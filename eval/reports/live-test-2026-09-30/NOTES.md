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

**02:09 — after the B+30 run (02:00): 7 of 7 predictions due so far met.** The run held the lease
02:00:20–02:01:30 and wrote no probe; the four Missoula Octobers and River Falls read `Waiting for
uploads to settle`. The boundary pair is in place: River Falls October's last upload was 01:58:08,
~32 minutes before the 02:30 run's clock, and Timber Place October's 02:03:08, ~27 minutes before.
**One plan error, no effect:** Timber Place has no distribution schedule in the June samples (the
first test's plan knew, `ds=False`); this plan asked accounting to upload one for Timber Place in
October (O6) and September (S7). O6's act failed at 02:03:08 while finding the local file
(`StopIteration`), before anything reached Drive; S7's will fail the same way at B+95.5. The
schedule is optional and no prediction depends on it, so the plan is left as committed.

**02:51 — after the B+60 run (02:30): 14 of 14 met.** The run held the lease 02:30:19–02:45:02
(14 min 43 s), wrote one probe (02:31:01, two seconds before its first build) and built five
October first reports from scratch, $2.26 in all: Fort Grounds 8 pages / 6 bookmarks with the
schedule that came 18 minutes after the rest (one version, not two); Lolo Peak Village 8/6;
Mullan Crossing 7/5, golden less the optional schedule; River Falls 29/13; WayPointe 10/8 — each
its golden shape. **D-26 is live:** River Falls was built by the first run ~32 minutes after its
last upload (01:58:08), where the old 60-minute window would have waited for 03:00; Timber Place,
~27 minutes, waits; and the status files now say "the first run 30 or more minutes after the
last upload". Stakeholder actions since: Mullan Crossing's schedule at 02:45:09; the reviewer
trashed Lolo Peak Village's v1 at 02:50:03.
