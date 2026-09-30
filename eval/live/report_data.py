"""Tables for a live test's report, from the evidence alone: events, snapshots and golden.

    uv run python eval/live/report_data.py      # prints them and writes tables.md

Nothing here reads Drive. A run is known by the lease a snapshot saw, so a run whose lease was
overwritten before the next snapshot (O5b's, by O5c's) has builds but no row of its own; those
builds are listed under "(lease not captured)".
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate
import which

REPO = which.REPO
OUT = which.OUT
DS = "cornerstone_distribution_schedule"


def _t(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _hms(value: str | None) -> str:
    return value[11:19] if value else "-"


def golden() -> dict[str, dict[str, int]]:
    """Pages and bookmarks per property; a bookmark per run of one section (and record)."""
    out: dict[str, dict[str, int]] = {}
    for path in sorted((REPO / "eval" / "golden").glob("*/*.json")):
        g = json.loads(path.read_text())
        runs, prev = 0, None
        for entry in g["expected_output"]:
            key = (entry["section"], entry.get("record"))
            runs += key != prev
            prev = key
        out[g["property_id"]] = {
            "pages": g["expected_output_page_count"],
            "bookmarks": runs,
            "ds_pages": sum(1 for e in g["expected_output"] if e["doc_role"] == DS),
        }
    return out


def _events(out: Path = OUT) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]


def _latest_snapshot() -> dict[str, Any]:
    paths = sorted((OUT / "snapshots").glob("2*.json"))
    return json.loads(paths[-1].read_text()) if paths else {}


def _index_entries(snap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Each version's entry in its month's index (inputs with upload times), by `prop|month|vN`."""
    out: dict[str, dict[str, Any]] = {}
    for prop, record in (snap.get("properties") or {}).items():
        for month, facts in record.get("months", {}).items():
            state = facts.get("state") or {}
            for entry in state.get("versions", []) if isinstance(state, dict) else []:
                out[f"{prop}|{month}|v{entry['version']}"] = entry
    return out


def _wait_minutes(entry: dict[str, Any] | None, run_start: datetime | None) -> str:
    """Minutes from the version's newest input upload to the start of the run that built it
    (what the settle window governs), then to the start of its build."""
    if not entry or not entry.get("inputs"):
        return "-"
    last = max(_t(i["uploaded_at"]) for i in entry["inputs"] if i.get("uploaded_at"))
    built = _t(entry.get("built_at"))
    if not (built and last):
        return "-"
    to_build = f"{(built - last).total_seconds() / 60:.0f}"
    if run_start is None:
        return to_build
    return f"{(run_start - last).total_seconds() / 60:.0f} / {to_build}"


def _classify_s(v: dict[str, Any]) -> str:
    ms = (v.get("timings_ms") or {}).get("classify")
    return f"{ms / 1000:.1f}" if ms is not None else "-"


def _shape(v: dict[str, Any], gold: dict[str, int]) -> str:
    pages, marks = v.get("pages"), v.get("bookmarks")
    if pages == gold["pages"] and marks == gold["bookmarks"]:
        return "= golden"
    omitted = v.get("omitted") or []
    if (
        any("distribution" in str(o).lower() for o in omitted)
        and pages == gold["pages"] - gold["ds_pages"]
        and marks == gold["bookmarks"] - 1
    ):
        return "= golden less the optional schedule"
    return f"≠ golden {gold['pages']}/{gold['bookmarks']}"


def tables() -> str:
    events = _events()
    gold = golden()
    versions = sorted(
        (e for e in events if e["kind"] == "version"), key=lambda e: e.get("built_at") or ""
    )
    leases: dict[tuple[str, str], dict[str, Any]] = {}
    for e in events:
        lease = e.get("lease")
        if str(e.get("tag", "")).startswith("after-cleanup"):  # taken after the test
            continue
        if e["kind"] in ("snapshot", "no_run") and lease and lease.get("acquired"):
            leases[(lease["host"], lease["acquired"])] = lease

    def run_of(v: dict[str, Any]) -> str:
        built = _t(v.get("built_at"))
        for (host, _), lease in leases.items():
            start, end = _t(lease["acquired"]), _t(lease.get("released"))
            if built and start and end and start <= built <= end:
                return host
        return "(lease not captured)"

    def run_start(v: dict[str, Any]) -> datetime | None:
        host = run_of(v)
        return next((_t(k[1]) for k in leases if k[0] == host), None)

    lines: list[str] = []

    # Runs
    lines += [
        "### Runs seen holding the lease",
        "",
        "| Host | Kind | Acquired | Released | Took | Builds | Model spend | Probes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    snap = _latest_snapshot()
    probes = [_t(p) for p in snap.get("probes_created") or []] if "probes_created" in snap else None
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for v in versions:
        by_run[run_of(v)].append(v)
    for (host, acquired), lease in sorted(leases.items(), key=lambda kv: kv[0][1]):
        start, end = _t(acquired), _t(lease.get("released"))
        secs = int((end - start).total_seconds()) if start and end else None
        took = f"{secs // 60}:{secs % 60:02d}" if secs is not None else "-"
        kind = "Azure, scheduled" if host.startswith("crr-quarterly-") else "Actions, forced"
        built = by_run.get(host, [])
        usd = sum(v.get("usd") or 0 for v in built)
        made = (
            "-"
            if probes is None or not (start and end)
            else str(sum(1 for p in probes if p and start <= p <= end))
        )
        lines.append(
            f"| `{host}` | {kind} | {_hms(acquired)} | {_hms(lease.get('released'))} | {took} "
            f"| {len(built)} | ${usd:.2f} | {made} |"
        )
    if by_run.get("(lease not captured)"):
        built = by_run["(lease not captured)"]
        lines.append(
            f"| (lease not captured) | | | | | {len(built)} "
            f"| ${sum(v.get('usd') or 0 for v in built):.2f} |"
        )
    lines.append("")

    # Versions
    lines += [
        "### Every version published",
        "",
        "| Built | Property | Month | v | State | Pages/bm | Shape | Title | Calls | $ | Reused "
        "| Classify s | Last upload → run / build, min | Review codes |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    entries = _index_entries(snap)
    for v in versions:
        g = gold[v["prop"]]
        title_ok = bool(v.get("title")) and str(v.get("file", "")).startswith(f"{v['title']} - v")
        lines.append(
            f"| {_hms(v.get('built_at'))} | {v['prop']} | {v['month'][:7]} | {v['version']} "
            f"| {v.get('state_status')} | {v.get('pages')}/{v.get('bookmarks')} | {_shape(v, g)} "
            f"| {'ok' if title_ok else 'CHECK'} | {v.get('calls')} | {(v.get('usd') or 0):.3f} "
            f"| {len(v.get('reused') or [])} | {_classify_s(v)} "
            f"| {_wait_minutes(entries.get(v['key']), run_start(v))} "
            f"| {', '.join(sorted(set(v.get('review_codes') or []))) or '-'} |"
        )
    lines.append("")

    # One-file rebuilds: the capacity change, against the first test where there is one
    quick = [v for v in versions if v.get("reused") and v.get("calls") == 1]
    first = REPO / "eval" / "reports" / "live-test-2026-09-29"
    before: dict[str, list[float]] = defaultdict(list)
    if first != OUT and (first / "events.jsonl").exists():
        for e in _events(first):
            ms = (e.get("timings_ms") or {}).get("classify")
            if e["kind"] == "version" and e.get("reused") and e.get("calls") == 1 and ms:
                before[e["prop"]].append(ms / 1000)
    if quick:
        lines += [
            "### One-file rebuilds (labels reused, one model call)",
            "",
            "| Property | Month | v | Reused docs | Classify s | Same property, 2026-09-29 |",
            "|---|---|---|---|---|---|",
        ]
        for v in quick:
            was = before.get(v["prop"])
            then = f"{min(was):.0f}-{max(was):.0f} s ({len(was)})" if was else "-"
            lines.append(
                f"| {v['prop']} | {v['month'][:7]} | {v['version']} | {len(v.get('reused') or [])} "
                f"| {_classify_s(v)} | {then} |"
            )
        lines.append("")

    # Spend
    total = sum(v.get("usd") or 0 for v in versions)
    calls = sum(v.get("calls") or 0 for v in versions)
    fresh = [v for v in versions if not v.get("reused")]
    partial = [v for v in versions if v.get("reused") and (v.get("calls") or 0) > 0]
    free = [v for v in versions if v.get("reused") and not v.get("calls")]
    by_month: Counter[str] = Counter()
    for v in versions:
        by_month[v["month"]] += v.get("usd") or 0
    lines += [
        "### Model spend",
        "",
        f"- {len(versions)} versions, {calls} model calls, **${total:.2f}** in all.",
        f"- Fresh builds (nothing reused): {len(fresh)}, "
        f"${sum(v.get('usd') or 0 for v in fresh):.2f}"
        + (
            f", median ${statistics.median(v.get('usd') or 0 for v in fresh):.2f} each"
            if fresh
            else ""
        )
        + ".",
        f"- Builds reusing some labels: {len(partial)}, "
        f"${sum(v.get('usd') or 0 for v in partial):.2f}; reusing all: {len(free)}, $0.",
        "- By month: " + ", ".join(f"{m} ${u:.2f}" for m, u in sorted(by_month.items())) + ".",
        "",
    ]

    # Actions
    acts = [e for e in events if e["kind"] == "act"]
    failed = [e for e in events if e["kind"] == "act_failed"]
    skipped = [e for e in events if e["kind"] == "act_skipped"]
    late = [e.get("late_s") or 0 for e in acts]
    lines += [
        "### Stakeholder actions performed",
        "",
        f"- {len(acts)} performed, {len(failed)} failed, {len(skipped)} skipped; "
        f"median {statistics.median(late) if late else 0:.0f} s after the planned minute, "
        f"worst {max(late) if late else 0} s.",
        "- By operation: "
        + ", ".join(f"{op} {n}" for op, n in Counter(e["op"] for e in acts).most_common())
        + ".",
        "- By who: "
        + ", ".join(f"{who} {n}" for who, n in Counter(e["who"] for e in acts).most_common())
        + ".",
        "",
    ]

    # Verdicts
    rows = evaluate.evaluate()
    counts = Counter(r["verdict"] for r in rows)
    lines += [
        "### Predictions",
        "",
        "- " + ", ".join(f"{k} {n}" for k, n in sorted(counts.items())) + f" (of {len(rows)}).",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    text = tables()
    (OUT / "tables.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
