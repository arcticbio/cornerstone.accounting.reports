"""Score the live test's snapshots against the predictions in plan.py.

    uv run python eval/live/evaluate.py          # prints the table, writes evaluation.md

Each prediction is checked against the snapshot taken after the run at its tick. A build that
lands one or two runs later (a busy run defers, SPEC §18.9 step 5) scores "late", not wrong.
Versions are counted from the month's index, never from PDFs lying in `output/`.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan

from crr.config import load_config

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "eval" / "reports" / "live-test-2026-09-29"
CONFIG = load_config(REPO / "config")


def _base() -> datetime:
    for line in (OUT / "events.jsonl").read_text().splitlines():
        event = json.loads(line)
        if event["kind"] == "start":
            return datetime.fromisoformat(event["base"].replace("Z", "+00:00"))
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
        "versions": len(versions),
        "entries": versions,
        "has_output": month.get("output") is not None,
        "components": sorted(month.get("components", {})),
        "siblings": sorted(months),
    }


def _matches(e: plan.Expect, facts: dict[str, Any] | None) -> bool:
    if e.sid == "A2":  # the system makes a proper folder beside the one a person made
        return facts is not None and "2026-08 August" in facts["siblings"]
    if e.sid in ("A3", "J1"):  # never read: no output folder is ever made in it
        return facts is not None and not facts["has_output"]
    if e.sid == "A1" and e.versions == 0:
        return facts is not None and len(facts["components"]) == 4 and facts["versions"] == 0
    if e.sid == "R1":
        return facts is not None and any(
            "reissued" in i.get("name", "") for v in facts["entries"] for i in v.get("inputs", [])
        )
    if facts is None:
        return False
    if e.status is not None and not (facts["status"] or "").startswith(e.status):
        return False
    return e.versions is None or facts["versions"] == e.versions


def evaluate() -> list[dict[str, Any]]:
    base = _base()
    snaps = _snapshots(base)
    rows = []
    for e in plan.EXPECTS:
        at = snaps.get(e.by)
        if at is None:
            verdict, facts = "pending", None
        else:
            facts = month_facts(at, e.prop, e.period)
            if _matches(e, facts):
                verdict = "met"
            else:
                later = [snaps[t] for t in (e.by + 30, e.by + 60) if t in snaps]
                if any(_matches(e, month_facts(s, e.prop, e.period)) for s in later):
                    verdict = "late"
                elif len(later) < 2 and e.sid != "R1":
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
                "verdict": verdict,
                "note": e.note,
            }
        )
    return rows


def main() -> None:
    rows = evaluate()
    lines = [
        "| Scenario | Property | Month | Tick | Expected | v | Actual | v | Verdict | Note |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['sid']} | {r['prop']} | {r['period']} | {r['tick']} | {r['expected']} "
            f"| {r['exp_v']} | {r['actual']} | {r['act_v']} | **{r['verdict']}** | {r['note']} |"
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
