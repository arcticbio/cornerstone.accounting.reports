# Live test 2026-09-29 — watchdog notes

Times UTC. B = 05:30. Each note is written by a half-hourly watchdog; the scored predictions
are in `evaluation.md` (from `eval/live/evaluate.py`).

- **06:15** · Conductor healthy (pid 420). 72/123 stakeholder actions done, 0 failed:
  September wave at 05:35 (29), October wave at 06:05, hand-made August/July folders at
  06:10. Runs observed: 05:30 `crr-quarterly-29844330` (lease 05:30:24–05:31:16) and 06:00
  `crr-quarterly-29844360` (06:00:23–06:01:35), both on the tick. 3/3 predictions due met:
  settling / waiting-for statuses exactly as SPEC §18.8 names them. $0 spent (nothing has
  settled yet). The one PDF in Salmon Crossing's September `output/` is the test's deliberate
  drop there, not a version.
- **06:43** · Conductor healthy; 76/123 actions, 0 failed. 06:30 run `crr-quarterly-29844390`
  (lease 06:30:23–06:32:15, 1 m 52 s: more months with files to read). 8/8 predictions due
  met. Hand-made folders behave as the code said they would: Fort Grounds' `2026-08 August`
  got its component folders and `output/` from the run (no status — its only file was dropped
  loose in the month folder); beside Lolo Peak's person-made `2026-08` the run created a
  proper `2026-08 August`, and the file in `2026-08` is never read; Mullan Crossing's
  `August 2026` and WayPointe's closed `2026-07 July` were left untouched (no `output/`).
  Every October month is settling. First builds are due in the 07:00 run.
- **07:20** · First builds. The 07:00 run `crr-quarterly-29844420` held the lease 07:00:24–07:14:57
  (14.5 min, inside the 20-min soft deadline) and built five September packages on
  `claude-opus-5-5`, $2.39 in all: Fort Grounds v1 (7 p / 5 bm — golden 8/6 less the absent
  optional schedule, $0.40), WayPointe v1 (10/8 = golden, $0.36), Timber Place v1 (25/13 =
  golden, OCR, $0.60), Bridgewater v1 **Needs review** (the P&L in the Balance Sheet folder:
  `unmapped_section`, `missing_required`; $0.54) and Salmon Crossing v1 **Built (current)**
  from Bridgewater's report (24 p / 8 bm — Bridgewater's shape, golden is 18/8; $0.49).
  River Falls held at the cost ceiling ($3.69 > $3.00), no model call. 15/15 predictions due
  met; 82/123 actions, 0 failed.
  **Finding F1 — another property's report is built as current, not flagged.** SPEC §18.6
  accepts that the folder is trusted, but a whole PM report for the wrong property passing
  the review gate is the case a reviewer is least likely to catch: the status says
  `Built v1 (current)`. Proposed fix: a review reason when no page's record label matches
  one of the property's configured `records[].pm_name` (the classifier already reads the
  `Property:` header per page), so it lands as `Needs review` instead.
