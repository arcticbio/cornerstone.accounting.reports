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
