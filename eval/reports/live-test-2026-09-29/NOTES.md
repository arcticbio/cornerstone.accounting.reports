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
- **07:43** · The 07:30 run `crr-quarterly-29844450` is still building at 07:43 (lease since
  07:30:24): October's eight properties all became ready together, the crunch by design. Its
  soft deadline (no new build after 20 min) should end it by ~07:56. The +130 actions ran at
  07:40 *during* that run (October: a schedule moved out of Lolo Peak, the whole Mullan
  Crossing report, a rename, a Google Doc, a shortcut, two Balance Sheets seconds apart at
  Bridgewater): whichever months the run had not yet reached will see those files before
  building, which is realistic and will show in the O-scenario scores. 92/123 actions, 0
  failed; $2.39 spent.
- **08:15** · **The October crunch, and the deferral working as designed.** The 07:30 run
  `crr-quarterly-29844450` (lease 07:30:24–07:50:41) started seven October builds back to back
  — Bridgewater 24/8, Fort Grounds 8/6, Lolo Peak 8/6, River Falls 29/13, Salmon Crossing 18/8,
  Timber Place 25/13 (all exactly golden) and Mullan Crossing's half report as **Needs review**
  (3 p, `missing_required`), as predicted. (`built_at` is when each build *started*.) Timber
  Place's OCR build ran from 07:46:46 to ~07:50:40; by then the 1200 s soft deadline had
  passed, so WayPointe October — settled since 07:07 — was deferred and built by the 08:00 run
  (10/8, golden). No duplicate anywhere. The 08:00 run `crr-quarterly-29844480`
  (08:00:23–08:07:27) also built Fort Grounds' hand-made **August** (7 p / 5 bm, no schedule)
  and Lolo Peak October **v2 for $0** — the schedule moved away to September, every page's
  labels reused. $6.23 spent; 94/123 actions, 0 failed.
  **Finding F2 (minor) — a deferred month keeps a stale status.** While deferred, WayPointe
  October still read `Waiting for uploads to settle`, though its files had settled 40 minutes
  earlier (§18.9 step 5 leaves the status as it is). A reviewer checking at 07:55 would be
  misled for one run. Proposed fix: write `Ready - building on the next run` for a month the
  soft deadline defers.
- **08:31** · Operator step O5a: *Run the Azure job* → `scheduled` dispatched on `main` at 08:31:49
  ([run 36543294733](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/36543294733))
  while the 08:30 scheduled run holds the lease. Expected: the manual execution finds the
  lease held and exits 0 with "nothing done". Result to follow from its logs.
- **08:36** · **O5a passed: two executions at once, one works.** The manual execution
  `crr-quarterly-h1oj2wx` (started 08:32:09) logged at 08:32:33 `intake.lease_held`
  `host=crr-quarterly-29844510-65mjq` and printed `nothing done: another run
  (crr-quarterly-29844510-65mjq) holds the lease until 2026-09-29 09:00 UTC`, then exited 0
  (Succeeded) — while the 08:30 scheduled run went on building. This is QUESTIONS A-14's
  first-week check, confirmed live on Azure: overlapping executions each see the lease and the
  second does nothing.
- **08:44** · The 08:30 run `crr-quarterly-29844510` (08:30:24–08:40:45) built four September
  versions, all exactly golden, corrections for cents: Bridgewater v2 with the right Balance
  Sheet (24/8, $0.017, 1 call, PM/P&L/schedule reused — the `Needs review` cleared), Fort
  Grounds v2 with the schedule (8/6, $0.022), River Falls v1 from the right report (29/13,
  $0.68) and Salmon Crossing v2 from its own report (18/8, $0.29, 15 calls). 35 predictions
  met, 1 late (the deferral), 0 missed; $7.24 spent; 100/123 actions, 0 failed.
  WayPointe September's "Update existing" with identical bytes (07:28) never disturbed the
  status — it read `Built v1 (current)` at 08:00 while the new revision was still settling, so
  an unchanged fingerprint outranks the settle window. Timber Place September's text file
  named `.pdf` is `Built v1 - newer files held`.
  **Finding F3 (minor) — a deleted published version goes unnoticed.** A reviewer trashed
  Salmon Crossing's October v1 at 08:10; the status still says `Built v1 (current)` for a
  report that no longer exists (predicted, per §18.7: nothing re-reads `output/`'s PDFs).
  Proposed fix: when the current version's PDF is missing, say so in the status
  (`Built v1 - report file missing`) so a reviewer knows to restore it from Trash.
- **08:59** · Operator step O5b: *Build a period* → `reconcile --force`, `timber-place`,
  `2026-10`, dispatched on `main` at 08:58:54
  ([run 36546168639](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/36546168639)),
  racing the 09:00 scheduled run for the lease. Result to follow.
- **09:08** · **O5b: the forced build won the race — and displaced the whole 09:00 run.**
  Run 36546168639 took the lease at 08:59:17 (host `5cced9db4683`, the runner's container),
  OCR'd Timber Place's scanned report, reused all three stored classifications (no model
  call), published `Built v2 (current)` (25 pages, 13 bookmarks, as v1) at 09:01:08, released
  the lease at 09:01:12 and exited 0. The lease shows no Azure run after it, so the 09:00
  scheduled execution — starting about 09:00:20, while the forced run held the lease — did
  nothing, as O5a showed it does. By design, then: one operator's forced build of one property
  stood the scheduled run down for all eight, so the builds due at 09:00 (S2, S5, O3, O6, O7)
  land at 09:30 and will score "late". Operator guidance for the RUNBOOK: dispatch a manual
  run a few minutes after :00/:30 has finished, never just before.
  The 09:30 prediction for O5 is amended from v2 to v3 before O5c runs (the plan's own note
  for O5c: "v3 if O5b already built v2"). Note on the image: `:build-v1` on `main` still
  probes at start (`repository.preflight_ok` 08:59:16) — the follow-up ec061b7 is not
  deployed, deliberately; the system under test stays fixed tonight.
- **09:14** · Watchdog: conductor alive (pid 420), 103/123 actions, 0 failed, $7.24. 09:10 acts
  done on time: S2's second upload of Lolo Peak Village's owner report under the same name, and
  S5's password-protected Balance Sheet into Timber Place September. The 09:00 tick is still
  open by design — the only lease since 08:30 is O5b's, taken before the tick — so its
  snapshot will be taken after O5c's run releases the lease (about 09:18), and will reflect
  that run, not a scheduled one.
- **09:17** · Operator step O5c: *Build a period* → `reconcile --force`, `timber-place`,
  `2026-10`, dispatched on `main` at 09:17:18 with the lease free (released 09:01:12)
  ([run 36548185639](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/36548185639)).
  Expected: v3 by reuse (O5b made v2). Result to follow.
- **09:20** · **O5c passed: a forced rebuild alone, v3 by reuse.** Run 36548185639 took the
  lease at 09:17:45 (host `6f4fcffad146`), reused all three stored classifications (no model
  call), published `Built v3 (current)` (25 pages, 13 bookmarks — identical in shape to v1 and
  v2) at 09:19:31 and released the lease at 09:19:35; the job took 2 min 20 s from dispatch,
  exit 0. Two forced rebuilds, both on stored labels: an operator can re-publish a month at
  no model cost. Aside for the report: both forced runs spent ~35 s between reusing the
  report's labels and the Balance Sheet's (09:18:44→09:19:19; 09:00:14→09:00:49) — not the
  model; worth a look at what the reuse path does per page for a 23-page scanned report.
- **09:21** · The ~35 s aside, explained: it is the orientation cross-check
  (`pipeline._classify` → `apply_orientation_check`: a 400 DPI render and a tesseract OSD pass
  per page, ~1.5 s a page), which runs on reused labels as well as fresh ones. Correct, and
  cheap next to a model call; a possible later saving is to skip it when the labels are
  reused for identical bytes. Not a defect.
