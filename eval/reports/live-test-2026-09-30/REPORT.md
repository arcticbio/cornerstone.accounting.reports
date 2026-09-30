# Live test of production — 30 September 2026

From 01:30 to 05:30 UTC, property managers, Cornerstone accounting and a reviewer worked in the
**production** Google Drive while the **live Azure schedule** ran `crr reconcile` every 30
minutes on its own. This second live test was four hours long and aimed at what changed after
the first one (29 September), all of it live since #21 was merged:

- the 30-minute settle window (D-26);
- the statuses for a month the 20-minute run limit defers (F2);
- the status for a published report that has gone missing (F3);
- reused labels not being cross-checked for orientation again (the capacity note);
- the documented Missoula exception to D-25;
- the publish probe written only by a run that builds (ec061b7).

It ran **hands off**, as the system will run in six months. There was no operator, no manual
or forced run, and no change to code, configuration or Azure during the test. Every file was a
**fresh export**: the June samples re-saved with their own metadata, so no upload shared bytes
with another or with the first test. They went into the September and October folders the
schedule itself had prepared. Nothing was carried over from the first test, whose months had
been moved out of production, so every first build classified from scratch.

The plan and all 64 predictions were committed before the test began (`eval/live/plan_0930.py`,
commit 9bc98f9). The conductor played the stakeholders at the planned minutes and photographed
Drive after every run (`eval/live/conductor.py`). The evidence is in this folder.

## Verdict

**Every change made since 29 September works in production, as specified.**

| | |
|---|---|
| Scheduled runs | 9, each taking the lease 19–22 s after its half hour; none failed. The busiest, 04:00, started seven fresh builds and deferred five months at its 20-minute limit (21 min 2 s in all). |
| Reports | 23 versions. Every one has its property's golden page and bookmark count, except two, both deliberate. Mullan Crossing October v1 lacks the optional schedule it was built without. Mullan Crossing September v1, built from another entity's report, went to review as documented. |
| Predictions | **64 of 64 met**, none late, withdrawn or amended. |
| Model spend | $7.81 over 364 calls: $0.34–0.71 for a report classified from scratch, 2 cents for a one-file correction. |
| Stakeholder actions | 72 planned: 70 performed, 2 failed before reaching Drive (a plan error, below). The first 14 landed 5–6.5 minutes late (Incidents, below); nothing predicted depended on them. |

## What each change did in production

**The 30-minute settle (D-26).**
- River Falls October's last file landed at 01:58:08, and the 02:30 run built it, 32 minutes
  later. The old 60-minute window would have waited until 03:00.
- Timber Place October's last file landed at 02:03:08. The 02:30 run found it 27 minutes old
  and waited; the 03:00 run built it.
- Every build the run limit did not defer came from a run that started 32–57 minutes after its
  month's last upload.
- The status files now say "the first run 30 or more minutes after the last upload".

**A deferred month says so (F2).** Quarter-end: every September file for the eight properties
and Cobalt's two Octobers landed between 03:05 and 03:09. The 04:00 run started seven fresh
September builds back to back; the seventh, Timber Place, started 16 min 15 s in. It then
deferred five months, and each status gives the reason: "this run reached its time limit before
it could start this build. The next run builds it."
- WayPointe September, Bridgewater October and Salmon Crossing October:
  `Ready - building on the next run`.
- Fort Grounds and WayPointe October, each with a correction waiting:
  `Built v1 - newer files ready, building next run`.
- The 04:30 run built all five.

**A missing report is named (F3).**
- A reviewer deleted Lolo Peak Village's published October v1 at 02:50.
- The 03:00 run's status read `Built v1 - report file missing`. It named the file and advised
  restoring it from the shared drive's Trash.
- The reviewer restored it at 03:10. The 03:30 run read `Built v1 (current)` again, with no new
  version.

**Reused labels are not cross-checked again (capacity).** A correction that changes one file
is classified with one model call; the other documents' labels are reused. Classifying such a
rebuild took seconds, against half a minute or more for the same properties on 29 September:

| Rebuild | Classify | Same property, 29 September |
|---|---|---|
| Mullan Crossing October v2 (schedule added) | 5.9 s | 31–33 s |
| Fort Grounds October v2 (Balance Sheet corrected) | 5.2 s | 29–31 s |
| WayPointe October v2 (P&L corrected) | 5.5 s | 28–30 s |
| Bridgewater September v2 (Balance Sheet reissued; 24-page report reused) | 11.9 s | 37–38 s |
| River Falls September v2 (Balance Sheet reissued; 29-page scan reused) | 6.2 s | 52 s |
| Timber Place September v2 (Balance Sheet reissued; 25-page scan reused) | 4.9 s | 44–46 s |

*Observation, not a defect:* on the two scanned McCathren reports, OCR still runs on every
build, even when the report's labels are reused. Timber Place's and River Falls' one-file
rebuilds spent 71 s and 97 s in OCR, against 5–6 s classifying, so each still took about two
minutes. The output needs the text layer (RUNBOOK: never skip OCR), so any saving would come from
keeping the OCR'd copy of an unchanged report. It only matters if crunches grow.

**The Missoula exception to D-25.**
- Missoula exported Lolo Peak Village's report and filed it as Mullan Crossing's September
  report.
- The 04:00 run built it as `Needs review (v1)`. Its four `unresolved_record` reasons each name
  "Lolo Peak Village LP" on a per-record section. Following from them, the review also lists two
  `missing_required` (the output's per-record items resolved to nothing) and three
  `unmapped_section`. The review PDF has 5 pages, against 8 for the real report.
- Missoula then uploaded the right report. The 05:00 run renamed the wrong one
  `SUPERSEDED - Mullan Crossing - Owner Report - September 2026.pdf` (set aside, not deleted).
  The 05:30 run built v2 from the right report as `Built v2 (current)`: 8 pages and 6 bookmarks,
  golden. The new report was classified from scratch (17 calls, $0.36), and the three
  Cornerstone files' labels were reused.
- The owner confirmed on 30 September that this check stays for all four Missoula properties
  (D-25).

**One publish probe per building run (ec061b7).** The three runs with nothing to build (01:30,
02:00 and 05:00) wrote no probe. Each of the six that built wrote exactly one, seconds before
its first build.

## Incidents

**The conductor was down from about 01:19 to 01:38.**
- What happened: the session driving the test went idle after the plan was committed, and its
  container was recycled. The conductor had been started detached, as a process the session
  did not track, so nothing held the session open; the first test's conductor was a tracked
  task and ran 7.5 hours on one start. The conductor was restarted from its event log at 01:38.
- Effect: the 14 October uploads planned for 01:32–01:33 landed 5–6.5 minutes late. No
  prediction depended on the difference: the 02:00 run still found them settling and the 02:30
  run settled.
- Change: a tracked watcher then held the session open, and the check-ins restart the conductor
  if it is ever found down.
- Not the system under test: the scheduled runs on Azure were unaffected.

**Two actions failed before reaching Drive, a plan error.** Timber Place has no distribution
schedule in the June samples; the first test's plan knew this and this plan did not. The two
uploads (October at 02:03, September at 03:07) failed while looking for the local file. The
schedule is optional, and no prediction depended on it.

## Predictions

**64 of 64 met.** Each was committed before the test, and none was withdrawn or amended during
it. Two accepted either of two outcomes by design: the 04:00 run's seventh and eighth builds
(Timber Place and WayPointe September) could fall either side of its 20-minute limit. The plan
estimated the seventh would start ~17 minutes in and the eighth would be deferred. Timber Place
started 16 min 15 s in, and WayPointe was deferred.

What the checks behind the predictions established, beyond each month's status and version
count:
- the late schedule was absorbed into Fort Grounds October v1, and Mullan Crossing October v1
  was built without its schedule;
- the F2 and F3 statuses give their reasons in the status text;
- Mullan Crossing September v1's review reasons include `unresolved_record`, and its wrong
  report was renamed `SUPERSEDED`;
- six one-file rebuilds classified in under 20 s each;
- every run wrote the predicted number of probes.

Full table: `evaluation.md`.

## Runs, reports and spend

The full tables are in `tables.md`: every run with its builds, spend and probes; every version
with its shape against golden, its classify time and the minutes from its last upload to its
run and build; and the one-file rebuilds against 29 September.

- **Runs:** 9 scheduled executions, 01:30 to 05:30, all seen holding the lease, 19–22 s after
  their tick. Three had nothing to build and took 54 s to 1 min 33 s. The six that built took
  2 min 12 s (one rebuild) to 21 min 2 s (the 04:00 crunch; its seventh build started 16 min 15 s
  in and finished past the limit, which only stops a run *starting* builds).
- **Spend:** $7.81 in all. 16 fresh builds cost $7.33 (median $0.41). Seven builds reusing some
  labels cost $0.48: six one-file rebuilds at 2 cents each, and Mullan Crossing September v2,
  whose new report was classified from scratch, $0.36. By month: September $4.07, October $3.74.
- **Timing on Azure:**
  - a run with nothing to build takes 1–1.5 minutes;
  - a fresh report takes 2–2.5 minutes, or 4.5–5 minutes for a scanned McCathren report
    (71–97 s of OCR);
  - a one-file correction takes 30–45 s, or about 2 minutes on a scanned report (its OCR).
- **Settle, measured:** every build the run limit did not defer came from a run that started
  32–57 minutes after its month's last upload. Its build started up to 16 minutes into that run.
  The five deferred months came one run later (70–82 minutes).

## What this test did not cover

- A Rent Manager rename of a single-entity Missoula property. This is the cost the owner accepted
  with D-25: its reports would go to review until `pm_name` is updated and the month rebuilt
  with `reconcile --force`. Neither the rename nor the forced rebuild was staged; a forced
  rebuild is an operator step, and this test had no operator.
- The review-state form of F3 (`Needs review (vN) - report file missing`), and the carry-over
  of an unsettled page's orientation reason when its labels are reused. Both are unit-tested
  only; no page in the samples is orientation-uncertain.
- Closing a month (42 days after month end) and its 14-day grace period.
- Real September and October exports; the June samples stood in.
- Outages of Drive, Azure or the model provider.

## Cleanup

At 05:39, with the 05:30 run finished and its lease released (05:37:37), `eval/live/cleanup.py`
moved the 16 September and October month folders the test used out of the production root and
into the rehearsal root, under the same property paths, each renamed with the suffix
` (live test 2026-09-30)`. Nothing was deleted. The folders keep their uploads, versions,
statuses and indexes, and the published reports can still be opened there. The record is
`cleanup.json`.

Right after the move, each property in production held only its original `2026-06 June` folder
(snapshot `after-cleanup-0540`). ⟨after 06:00⟩

Left in place: the six publish probes the runs trashed stay in the shared drive's Trash, which
Drive empties after 30 days. The test itself left nothing there, because the one report it
deleted was restored.

## Evidence

| File | What it is |
|---|---|
| `events.jsonl` | every action performed and every observation, in order |
| `snapshots/` | Drive after each run: files, statuses (with their text), month indexes, probes |
| `NOTES.md` | the check-in log, written as the test ran |
| `evaluation.md` | every prediction scored (`eval/live/evaluate.py`) |
| `tables.md` | runs, versions against golden, one-file rebuilds, spend, actions (`eval/live/report_data.py`) |
| `cleanup.json` | what the cleanup moved, and where |
