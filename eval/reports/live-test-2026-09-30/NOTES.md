# Live test of production, 30 September 2026 — notes as it ran

B = **01:30 UTC**; the last observed run is B+240 = 05:30. The plan and every prediction are in
`eval/live/plan_0930.py`, committed before B. The conductor
(`uv run python eval/live/conductor.py run --base 2026-09-30T01:30:00Z`) plays the stakeholders
and snapshots Drive after each run; nothing else touches production during the test.

Before B (01:00–01:10): production's September and October folders hold no files (all 16
component sets present, empty); the root holds only the three manager folders, the lease and the
summary. The deployed image is the one CI published at 00:00 UTC from `main` (#21). Harness smoke
in the rehearsal root: a fresh export, a file trashed from `output/` and restored from the Trash,
the probe count — all worked.

Watchdog entries below are added as the test runs.

**01:39 — the conductor was down from ~01:19 to 01:38; restarted, no prediction affected.** Its
last heartbeat was 01:18:40: the session's container was recycled after the session went idle,
and the conductor, started detached, was not a task the harness tracks, so nothing held the
session open (the first test's conductor was a tracked task, which is why it ran 7.5 h on one
start). It missed the B+0 tick and the uploads planned for B+2 to B+3.5. Restarted at 01:38:20
from `events.jsonl`: the 14 October uploads landed 01:38:32–01:39:15, 299–389 s late. Nothing
predicted depends on them landing before B+8.5 — the B+30 run still sees them ~21 minutes old
(settling) and the B+60 run ~51 (settled). The B+0 run's snapshot is taken after these uploads,
but its lease window (01:30) is unchanged, so its probe count still scores that run. A tracked
background watcher now holds the session open for as long as the conductor runs, and wakes this
session the moment it exits.
