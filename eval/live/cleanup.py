"""After the live test: move its months out of the production root, into the rehearsal root.

    uv run python eval/live/cleanup.py --dry-run   # say what would move
    uv run python eval/live/cleanup.py             # move it

Nothing is deleted: every test month folder — September and October, and the month folders
made by hand (August, a misnamed August, July) — moves whole, with its uploads, versions,
statuses and index, to the same manager/property path under the rehearsal root, renamed
"<name> (live test 2026-09-29)". Files the test dropped straight into a property folder go the
same way. The next scheduled run then recreates empty September and October folders in
production and rewrites the summary without them.

It moves nothing while a run holds the lease, nor in the minutes around a half-hour tick, so no
reconcile ever sees a month disappear under it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conductor

from crr.repository.drive_client import RETRIES

REHEARSAL_ROOT = "1eGZGlv5IGVd7OGM0-_2jcDfa56FkwAlz"
SUFFIX = " (live test 2026-09-29)"
TEST_MONTHS = (
    "2026-09 September",
    "2026-10 October",
    "2026-08 August",
    "2026-08",
    "August 2026",
    "2026-07 July",
)
DROPPED = "(dropped in the property folder)"


def _quiet_moment(prod: conductor.Drive) -> None:
    """Wait until no run holds the lease and the next tick is at least 4 minutes away."""
    deadline = time.monotonic() + 40 * 60
    while time.monotonic() < deadline:
        lease = conductor.lease(prod)
        held = bool(lease and not lease.get("released"))
        minute = conductor.now().minute % 30
        if not held and 2 <= minute <= 25:
            return
        time.sleep(20)
    raise RuntimeError("no quiet moment in 40 minutes: a run still holds the lease")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    prod = conductor.Drive(conductor.Settings().gdrive_root_folder_id or "")
    rehearsal = conductor.Drive(REHEARSAL_ROOT)
    plan: list[dict[str, Any]] = []
    for entry in conductor.CONFIG.properties.properties:
        src = prod.property_id(entry.id)
        dst = rehearsal.property_id(entry.id)
        for child in prod.children(src):
            if (child.is_folder and child.name in TEST_MONTHS) or DROPPED in child.name:
                plan.append(
                    {
                        "prop": entry.id,
                        "id": child.id,
                        "name": child.name,
                        "to": child.name + SUFFIX,
                        "src": src,
                        "dst": dst,
                    }
                )
    for item in plan:
        print(f"{item['prop']:<18} {item['name']!r} -> rehearsal {item['to']!r}")
    if args.dry_run:
        print(f"{len(plan)} item(s) would move; nothing moved (dry run)")
        return
    _quiet_moment(prod)
    moved = []
    for item in plan:
        prod.svc.files().update(
            fileId=item["id"],
            addParents=item["dst"],
            removeParents=item["src"],
            body={"name": item["to"]},
            supportsAllDrives=True,
            fields="id",
        ).execute(num_retries=RETRIES)
        moved.append(
            {k: item[k] for k in ("prop", "name", "to", "id")}
            | {"at": conductor.iso(conductor.now())}
        )
    out = conductor.OUT / "cleanup.json"
    out.write_text(json.dumps(moved, indent=1))
    print(f"{len(moved)} item(s) moved to the rehearsal root; record in {out}")


if __name__ == "__main__":
    main()
