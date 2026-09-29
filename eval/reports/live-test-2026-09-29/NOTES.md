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
