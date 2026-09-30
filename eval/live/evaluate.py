"""Score a live test's snapshots against the predictions in its plan (`which.py` picks the test).

    uv run python eval/live/evaluate.py          # prints the table, writes evaluation.md

Each prediction is checked against the snapshot taken after the run at its tick. A build that
lands one or two runs later (a busy run defers, SPEC §18.9 step 5) scores "late", not wrong.
Versions are counted from the month's index, never from PDFs lying in `output/`.

A prediction may claim one further fact (`Expect.check`):

- `omitted:none` / `omitted:some` — the version was built with / without an optional file;
- `codes:<code>` — the version's review reasons include `<code>`;
- `classify_max_s:<n>` — the version's classify step took at most `<n>` seconds;
- `body:<text>` — the month's status file says `<text>`;
- `superseded:<text>` — a file in the month is named `SUPERSEDED - …<text>…`;
- `probes:<n>` — the run at the tick wrote `<n>` publish probes (prop and period are `*`).

A status of `A|B` accepts either headline.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import which

from crr.config import load_config

plan = which.plan
REPO = which.REPO
OUT = which.OUT
CONFIG = load_config(REPO / "config")
SUPERSEDED = "SUPERSEDED - "


def _t(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _events() -> list[dict[str, Any]]:
    return [json.loads(line) for line in (OUT / "events.jsonl").read_text().splitlines()]


def _base() -> datetime:
    for event in _events():
        if event["kind"] == "start":
            return _t(event["base"])
    raise SystemExit("no start event")


def _snapshots(base: datetime) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for path in sorted((OUT / "snapshots").glob("2*.json")):
        snap = json.loads(path.read_text())
        if "offset" in snap:
            out[int(snap["offset"])] = snap
        else:  # the baseline has no offset recorded if taken by hand
            tick = datetime.strptime(path.stem, "%Y%m%d-%H%M").replace(tzinfo=base.tzinfo)
            out[int((tick - base).total_seconds() // 60)] = snap
    return out


def _versions() -> dict[str, dict[str, Any]]:
    """What the conductor read from each version's manifest and PDF, by `prop|month|vN`."""
    return {e["key"]: e for e in _events() if e["kind"] == "version"}


def _folder(period: str) -> str:
    return (
        period.split(":", 1)[1]
        if period.startswith("folder:")
        else (CONFIG.properties.period_folder(period))
    )


def month_facts(snap: dict[str, Any], prop: str, period: str) -> dict[str, Any] | None:
    months = snap["properties"].get(prop, {}).get("months", {})
    month = months.get(_folder(period))
    if month is None:
        return None
    output = month.get("output") or {}
    state = month.get("state") or {}
    versions = state.get("versions", []) if isinstance(state, dict) else []
    return {
        "status": (output.get("status") or [None])[0],
        "statuses": output.get("status") or [],
        "body": "\n".join(output.get("status_body") or []),
        "versions": len(versions),
        "entries": versions,
        "has_output": month.get("output") is not None,
        "components": sorted(month.get("components", {})),
        "files": [f["name"] for files in month.get("components", {}).values() for f in files],
        "siblings": sorted(months),
    }


def _probes(snap: dict[str, Any]) -> tuple[bool, int]:
    """Whether the tick's run was seen, and how many probes were made while it held the lease."""
    lease = snap.get("lease") or {}
    if not snap.get("run_observed") or not lease.get("acquired") or not lease.get("released"):
        return False, 0
    start = _t(lease["acquired"]) - timedelta(seconds=5)
    end = _t(lease["released"]) + timedelta(seconds=5)
    made = [p for p in snap.get("probes_created") or [] if start <= _t(p) <= end]
    return True, len(made)


def _check(
    e: Any, facts: dict[str, Any] | None, snap: dict[str, Any], versions: dict[str, Any]
) -> tuple[bool, str]:
    """The prediction's further fact, and what was seen."""
    kind, _, arg = e.check.partition(":")
    if kind == "probes":
        seen, made = _probes(snap)
        return seen and made == int(arg), f"{made} probe(s)" if seen else "run not seen"
    if facts is None:
        return False, "no month"
    if kind == "body":
        return arg in facts["body"], "said" if arg in facts["body"] else "not said"
    if kind == "superseded":
        hits = [n for n in facts["files"] if n.startswith(SUPERSEDED) and arg in n]
        return bool(hits), hits[0] if hits else "no superseded file"
    v = versions.get(f"{e.prop}|{_folder(e.period)}|v{e.versions}")
    if v is None:
        return False, f"no v{e.versions}"
    if kind == "codes":
        codes = v.get("review_codes") or []
        return arg in codes, ", ".join(codes) or "no review codes"
    if kind == "omitted":
        omitted = v.get("omitted") or []
        return (not omitted) if arg == "none" else bool(omitted), f"omitted {omitted or 'none'}"
    if kind == "classify_max_s":
        ms = (v.get("timings_ms") or {}).get("classify")
        if ms is None:
            return False, "no timing"
        return ms <= float(arg) * 1000, f"classify {ms / 1000:.1f} s"
    raise ValueError(f"unknown check {e.check!r}")


def _matches(
    e: Any, facts: dict[str, Any] | None, snap: dict[str, Any], versions: dict[str, Any]
) -> tuple[bool, str]:
    if which.NAME == "2026-09-29":  # the first test's folder scenarios
        if e.sid == "A2":  # the system makes a proper folder beside the one a person made
            return facts is not None and "2026-08 August" in facts["siblings"], ""
        if e.sid in ("A3", "J1"):  # never read: no output folder is ever made in it
            return facts is not None and not facts["has_output"], ""
        if e.sid == "A1" and e.versions == 0:
            ok = facts is not None and len(facts["components"]) == 4 and facts["versions"] == 0
            return ok, ""
        if e.sid == "R1":
            return facts is not None and any(
                "reissued" in i.get("name", "")
                for v in facts["entries"]
                for i in v.get("inputs", [])
            ), ""
    if e.check.startswith("probes:"):
        return _check(e, facts, snap, versions)
    if facts is None:
        return False, ""
    if e.status is not None and not any(
        (facts["status"] or "").startswith(s) for s in e.status.split("|")
    ):
        return False, ""
    if e.versions is not None and facts["versions"] != e.versions:
        return False, ""
    if e.check:
        return _check(e, facts, snap, versions)
    return True, ""


def evaluate() -> list[dict[str, Any]]:
    base = _base()
    snaps = _snapshots(base)
    versions = _versions()
    rows = []
    for e in plan.EXPECTS:
        at = snaps.get(e.by)
        run_level = e.check.startswith("probes:")
        evidence = ""

        def facts_at(snap: dict[str, Any], e: Any = e, run_level: bool = run_level) -> Any:
            return None if run_level else month_facts(snap, e.prop, e.period)

        if e.withdrawn:  # unreachable once the run changed course; shown, never scored
            verdict, facts = "withdrawn", facts_at(at) if at else None
        elif at is None:
            verdict, facts = "pending", None
        else:
            facts = facts_at(at)
            ok, evidence = _matches(e, facts, at, versions)
            if ok:
                verdict = "met"
            elif run_level:
                verdict = "MISSED"
            else:
                later = [snaps[t] for t in (e.by + 30, e.by + 60) if t in snaps]
                if any(_matches(e, facts_at(s), s, versions)[0] for s in later):
                    verdict = "late"
                elif len(later) < 2 and e.sid != "R1" and e.by + 60 <= plan_end():
                    verdict = "not yet"
                else:
                    verdict = "MISSED"
        rows.append(
            {
                "sid": e.sid,
                "prop": e.prop,
                "period": e.period,
                "by": e.by,
                "tick": (base + timedelta(minutes=e.by)).strftime("%H:%M"),
                "expected": e.status or "-",
                "exp_v": "-" if e.versions is None else e.versions,
                "actual": (facts or {}).get("status") or "-",
                "act_v": (facts or {}).get("versions", "-"),
                "check": f"{e.check} → {evidence}" if e.check else "",
                "verdict": verdict,
                "note": f"{e.note} — withdrawn: {e.withdrawn}" if e.withdrawn else e.note,
            }
        )
    return rows


def plan_end() -> int:
    return int(getattr(plan, "END_OFFSET", 450))


def main() -> None:
    rows = evaluate()
    lines = [
        "| Scenario | Property | Month | Tick | Expected | v | Actual | v | Check | Verdict "
        "| Note |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['sid']} | {r['prop']} | {r['period']} | {r['tick']} | {r['expected']} "
            f"| {r['exp_v']} | {r['actual']} | {r['act_v']} | {r['check']} "
            f"| **{r['verdict']}** | {r['note']} |"
        )
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    text = "\n".join([f"Scored {len(rows)} predictions — {summary}", "", *lines, ""])
    (OUT / "evaluation.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
