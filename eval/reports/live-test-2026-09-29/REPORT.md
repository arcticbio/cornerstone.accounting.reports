# Live test of production — 29 September 2026

From 05:30 to 13:00 UTC a scripted cast of stakeholders worked in the **production** Google
Drive while the **live Azure schedule** ran `crr reconcile` every 30 minutes on its own. The cast
was three property-management companies, Cornerstone accounting, a reviewer and an operator.
They performed 123 actions at planned minutes: uploads, re-uploads, corrections and
withdrawals, wrong folders and wrong files, moves, renames, a Google Doc, a shortcut and
deletions. Nothing about the system under test was changed or helped along: no code, template
or Azure change during the test. The only runs started by hand were the operator steps the
plan called for.

Published as a page: https://claude.ai/artifact/RuDow4jqiMmj8ZdzLWrkLB (private to the owner until shared).

> **Updated 2026-09-29, after the owner's review.** F1 is accepted by design: the folder declares
> which property a file belongs to (D-25, SPEC §18.6). F2, F3 and the capacity note are fixed in
> the follow-up PR; F4 and F5 were documented in #20 and the probe change (ec061b7) is live
> (the 17:30 and 18:00 runs left no probe). The findings below say what was done about each.

The plan, with every prediction, was committed before the test began (`eval/live/plan.py`). A
conductor performed the actions and photographed Drive after every run (`eval/live/conductor.py`).
The evidence is in this folder.

## Verdict

**The live system is ready for real uploads.**

| | |
|---|---|
| Scheduled runs | 16, each taking the lease 22–24 s after its half hour; none failed. 09:00 stood down because an operator's forced build held the lease (by design, F4). The busiest run, sixteen rebuilds at once, took 19 min 38 s, inside the 20-minute limit. |
| Reports | 45 versions published. Every one has its property's golden page and bookmark count, except where the test fed in a deliberately wrong file. Those were held or sent to review, except another property's report, which is built as given — accepted by design (F1). |
| Predictions | 64 of 68 scored were met; 3 landed one run late, for reasons below; 1 was my error about the settle clock. 3 more were withdrawn mid-test, each before the run that would have scored it. |
| Model spend | $8.81 over 415 calls (budget $100): about $0.40 for a report classified from scratch, about 2 cents for a one-file correction, and nothing for a rebuild on stored labels. |
| Stakeholder actions | 123 performed, 0 failed; median 11 s after the planned minute. |

**F1 was the one finding that looked like a go-live blocker; the owner accepted it by design.**
A report filed under the wrong property is built as that property's, as a wrong or wrong-month
document already is: the reviewer is the check, and the right upload replaces it with the next
version. F2–F5 and the capacity note are done.

## What the stakeholders did, and what the system did

The June sample files stood in for September and October.

| Scenario | What people did in Drive | What the system did |
|---|---|---|
| S1 Fort Grounds Sep | An orderly month; the optional schedule an hour later; a revised Balance Sheet; then the revision deleted | v1 without the schedule → v2 with it (labels reused) → v3 revised → v4 back on v2's files, the old file's name restored |
| S2 Lolo Peak Sep | Files hours apart; a schedule moved in from October; the same report uploaded again under the same name ("Keep both") | Waited for each; waited again for the re-upload to settle; v1 from the newer copy, the older renamed `SUPERSEDED - …` |
| S3 Mullan Crossing Sep | Uploads dripping in under an hour apart, then a corrected P&L | Kept waiting to settle; built once, with the correction |
| S4 WayPointe Sep | Drive's "Update existing" with identical bytes two minutes before a run, later with changed bytes | No rebuild for identical bytes; v2 for changed |
| S5 Timber Place Sep | A scanned report; a text file named `.pdf`; a password-protected PDF; each deleted again | Built with OCR; each bad file held with a status saying why; back to v1 once deleted |
| S6 River Falls Sep | A 120-page unrelated PDF, a Word file and a photo in the report folder, then the right report | Held at the $3 cost ceiling with no model call; non-PDFs ignored; built from the right report |
| S7 Bridgewater Sep | The P&L uploaded into the Balance Sheet folder, then the right sheet | **Needs review**, then a clean v2 |
| S8 Salmon Crossing Sep | Another property's report; files dropped outside the component folders | **Built as current from the wrong report (F1)**; loose files ignored; v2 from the right report |
| O1–O8 October | A second month 30 minutes behind: a report split in two; a schedule moved to September; a rename, a Google Doc and a shortcut; two Balance Sheets seconds apart; a correction after the build; a reviewer deleting the published v1 | Half a report → review, then v2 from the whole; the move rebuilt October on reused labels ($0); rename/Doc/shortcut changed nothing; the later sheet won; each correction cost one call; the deleted v1 went unnoticed (F3) |
| O5a · O5b · O5c | The operator ran the Azure job by hand during a run; forced a build racing the 09:00 run; forced one alone | One run at a time in every case; both forced builds reused every label |
| A1–A3 · J1 | Month folders made by hand: `2026-08 August`, `2026-08`, `August 2026`, a closed `2026-07 July` | Adopted and built the proper one; made a proper folder beside the near miss; never read the others |
| R1 | Cornerstone reissued all sixteen Balance Sheets within two minutes (10:45) | All sixteen months waited, then the 12:00 run rebuilt all sixteen: 17 calls, $0.31 |

## How the live system behaved

- **On time.** Every scheduled execution took the lease 22–24 s after its tick.
- **One run at a time.**
  - O5a: a manual Azure execution started at 08:32, while the 08:30 run was building. It
    logged `intake.lease_held`, printed "nothing done" and exited 0, which confirms QUESTIONS
    A-14 live.
  - O5b: a forced Actions build dispatched at 08:58 took the lease at 08:59:17, so the
    09:00 run stood down for every property (F4).
  - O5c: a forced build alone published v3 of Timber Place October from stored labels.
- **Crunches are absorbed.**
  - October's eight properties settled together. The 07:30 run started seven builds back to
    back and stopped starting new ones at the 20-minute limit. The 08:00 run built the eighth.
  - The R1 reissue made sixteen months due at once. The 12:00 run built all sixteen; its last
    build started 77 s before the limit.
- **Nothing is built from a file still arriving.** The settle window is judged against the
  run's start time, so a file uploaded during a run is never "settled" by it. A report
  appears 60–90 minutes after the month's last upload, plus the build (F5).
- **Superseded files are labelled in Drive.** An older copy is renamed `SUPERSEDED - …` as
  soon as a newer one appears. If the newer one is deleted, the old name comes back. Renames
  never restart the settle clock.
- **Build order is month-major.** September's builds run first, then October's, each
  alphabetical by property.

## Findings

**F1 — another property's report is published as current.** *Accepted by design (D-25,
SPEC §18.6), owner decision 2026-09-29.*
- **What happened:** Salmon Crossing September v1 was built from Bridgewater's report. Its
  status read `Built v1 (current)`, with 24 pages where Salmon Crossing's golden report has 18.
- **Why nothing caught it:** nothing is meant to. The only name the system matches is a Rent
  Manager page's `Property:` line, which it needs to split WayPointe's report between two
  records (SPEC §5 rule 3); as a side effect that also sends a Missoula report for another
  entity to review. Cobalt's and McCathren's schemas carry no record qualifier at all (every
  section `cardinality: one`), and neither do Cornerstone's own files, so for Bridgewater,
  Salmon Crossing, Timber Place, River Falls and every Balance Sheet, P&L and schedule, the
  folder is the only statement of which property a file is for. (The first version of this
  report named only Cobalt; McCathren and Cornerstone's files are in the same position.)
- **Considered and declined:** a check that at least one page names the property. Managers
  name a property their own way (`405 - Salmon Crossing - 2000 SW Salmon Ave Redmond, OR
  97756`, `Timber Place by the Lake (1000)`), scans garble names (McCathren's schema notes
  "limber Place by the Lake"), and names change, so it would hold genuine reports and ask
  stakeholders to change how they work. The reviewer is the check; the right upload replaces a
  misfiled report with the next version (Salmon Crossing's v2 cost $0.29).

**F2 — a month the time limit defers keeps a stale status.** *Minor.*
- **What happened:** WayPointe October read `Waiting for uploads to settle` for one run after
  its files had settled.
- **Fixed** in the follow-up PR: a deferred month now reads `Ready - building on the next run`,
  or `Built vN - newer files ready, building next run` while an earlier version stands (SPEC
  §18.8, §18.9 step 5).

**F3 — a deleted published report goes unnoticed.** *Minor.*
- **What happened:** a reviewer trashed Salmon Crossing's October v1. The status went on
  saying `Built v1 (current)` until v2 replaced it. Numbering was right: the next version was
  v2, because versions come from the month's index.
- **Fixed** in the follow-up PR: when nothing has changed since the standing version but its
  PDF is no longer in `output/`, the status reads `Built vN - report file missing` and names
  the file and the two ways back — restore it from Trash, or force a rebuild. Nothing is
  rebuilt on its own. It costs one listing of `output/` per month with a version, per run.

**F4 — a manual run just before :00 or :30 delays everyone.** *Operator guidance, in the
RUNBOOK since #20.*
- **What happened:** the lease covers the whole drive, by design. O5b's forced build of one
  property made the 09:00 run stand down for all eight, and five builds waited until 09:30.

**F5 — the spec did not say which clock the settle window uses.** *Spec wording, in SPEC
§18.5 since #20.*
- **What happened:** River Falls October waited at 10:30 because its 09:31:12 file was 59 min
  11 s old at the run's start. That is consistent, but "within the last 60 minutes" did not
  say from when.

**Capacity note (not a defect).**
- **What happened:** sixteen one-call rebuilds took 19 min 38 s. The classify step took
  567 s, almost all of it the orientation cross-check (a 400 DPI render plus a tesseract pass,
  ~1.5 s a page) over 259 pages whose labels were reused. OCR of the two scanned reports took
  70–95 s each. Drive I/O was ~400 s.
- **Done** in the follow-up PR: labels reused for identical bytes are no longer cross-checked
  again — they were checked when made, and the stored labels carry the corrections — while
  anything the earlier check left unsettled is raised again (SPEC §7.6, §18.7). That removes
  most of the classify step from a crunch like this one.
- **Related:** the publish-probe change (ec061b7: a probe only in a run that builds) was
  deliberately not deployed during the test. It shipped with #20: the first runs after the
  merge, 17:30 and 18:00, left no probe, where every run before them had left one.

## Predictions that were not met

Every prediction was committed before the test. Every change during the test is dated in
`plan.py` and in `NOTES.md` and was made before the run it predicts.

- **Late (3):**
  - O4 WayPointe Oct: deferred by the 20-minute limit, as designed.
  - O3 Mullan Crossing Oct and O7 Bridgewater Oct: built at 09:30 because O5b displaced the
    09:00 run.
- **Withdrawn (3):** S2, S5 and O6 at 09:00. After the displacement, uploads at 09:10 and
  09:31 restarted those months' settle windows before any run could see them. They are shown
  in `evaluation.md` with the reason and not scored.
- **Amended before their runs (3):**
  - O5 at 09:30: v2 → v3, because O5b had already built v2 (the plan's own note for O5c
    anticipated this).
  - S2 at 10:30: v2 → v1, because there was no v1 at 09:00.
  - S5 at 11:00: → `newer files waiting`. This was a plan error: R1's reissue at 10:45 lands
    in that month too.
- **Wrong (1):** O6 River Falls Oct at 10:30. I assumed the settle clock ran until the run
  reached the month; the system fixes it at the run's start (F5).

Full table: `evaluation.md`.

## Runs, reports and spend

The full tables are in `tables.md`: every run seen holding the lease, every version with its
shape against golden, and spend by month.

- **Runs:** 16 scheduled executions, 05:30 to 13:00. Fifteen were seen holding the lease; the 09:00 run stood down while O5b's forced build held it. Eight runs built something; seven had nothing to build and took 52 s to 2 min 42 s. Two forced Actions builds (O5b, O5c) took about 2 minutes each. The longest runs were 07:30 (20 min 17 s: its last build, started before the limit, ran on past it) and 12:00 (19 min 38 s).
- **Spend:** $8.81 in all. There were 17 fresh builds for $7.73 (median $0.40), 25 builds
  reusing some labels for $1.09, and 3 reusing all labels for $0. By month: August $0.38,
  September $4.42, October $4.02.
- **Timing on Azure:**
  - a run with nothing to build takes 1–2 minutes;
  - a fresh report takes 2–5 minutes;
  - a one-file correction takes about a minute;
  - a scanned report adds 70–95 s of OCR.

## What this test did not cover

- Closing a month (42 days after month end) and its 14-day grace period.
- Real September and October exports; the June samples stood in.
- Outages of Drive, Azure or the model provider. Retries and the failure cap are unit-tested
  only.
- People editing the index or status files by hand.
- Weeks of history across many open months. No-op cost at scale was measured in the Phase 10
  audit.

## Cleanup

At 13:03, with the 13:00 run finished and its lease released, `eval/live/cleanup.py` moved
everything the test created out of the production root and into the rehearsal root, under the
same property paths, each renamed with the suffix ` (live test 2026-09-29)`. It moved 22 items
and deleted nothing:

- the September and October month folders of all eight properties (16);
- the hand-made `2026-08 August` folders of Fort Grounds and Lolo Peak, Lolo Peak's `2026-08`,
  Mullan Crossing's `August 2026` and WayPointe's `2026-07 July` (5);
- the P&L dropped loose in Salmon Crossing's property folder (1).

The record is `cleanup.json`. Right after the move, each property in production held only its
original `2026-06 June` folder, and the root only the three company folders, the lease file and
the summary (snapshot `after-cleanup-1305`). After the next scheduled run (13:30:27–13:34:15, host `crr-quarterly-29844810`), every property again has an empty `2026-09 September` and `2026-10 October` — four empty component folders and an empty `output/` each, no status — beside its untouched June folder, and the root summary reads *Last checked 2026-09-29 13:30 UTC* with no property lines: production is back to the state stakeholders will start from (snapshot `after-cleanup`).

Left in place: files the test moved to Trash stay in the shared drive's Trash, which Drive empties
after 30 days (the service account can trash but not delete). The published reports went with
their month folders to the rehearsal root, where they can still be opened.

## Evidence

| File | What it is |
|---|---|
| `events.jsonl` | every action performed and every observation, in order |
| `snapshots/` | Drive after each run: files, statuses, month indexes |
| `NOTES.md` | the half-hourly watchdog log, written as the test ran |
| `evaluation.md` | every prediction scored (`eval/live/evaluate.py`) |
| `tables.md` | runs, versions against golden, spend, actions (`eval/live/report_data.py`) |
| `cleanup.json` | what the cleanup moved, and where |
