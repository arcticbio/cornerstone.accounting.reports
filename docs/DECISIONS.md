# Decision log

Decisions already made. Do not re-open these without a new entry that supersedes the old one.
Format: id, decision, why, consequences. Newest at the bottom.

---

**D-01 · Vision model classifies; deterministic code composes.**
The model's only job is to label pages (section, continuation, record, orientation, confidence).
Ordering, selection, rotation and PDF assembly are pure functions of the labels and the output
definition. *Why:* replayable, auditable, testable without a model; a wrong label is visible in
the manifest rather than buried in the output. *Consequence:* no free-text instructions to the
model about what to include; that lives in `config/outputs/`.

**D-02 · One source schema per producing system, one output definition per property manager.**
The three managers share almost nothing; a unified schema would be a lie. *Consequence:* a new
manager is a new schema file + output file + golden labels, not code.

**D-03 · The published June 2026 packages are a soft target.**
Where a published package contains material with no available source — the separately-run Rent
Manager Balance Sheets on all four Missoula properties — the output omits it. No exception
handling, no synthesis. *Why:* the user's explicit direction; a system that reproduces
unavailable content is a system that fabricates. *Consequence:* Missoula output is
front matter + P&L Comparison + Unit Availability + Owner Statement. The
`rentmanager-missoula.balance_sheet` section stays declared (so the classifier recognises it)
and is listed in `drop`.

**D-04 · Vision on every page, with extracted/OCR text as a second channel.**
Regex is not the primary detector. *Why:* the user's direction; adapts to template drift and to
scanned sources. *Consequence:* McCathren requires OCR before the text channel exists;
Cobalt/Missoula get free text.

**D-05 · Footer text is a checksum on the classifier, never an override.**
When a footer names a report and the label disagrees, the build goes to review. The footer
does not win automatically. *Why:* keeps one source of truth; a footer regex that drifts should
surface as noise, not silently steer output.

**D-06 · Cornerstone front matter always leads: Balance Sheet, P&L YTD, Distribution Schedule.**
WayPointe's published June package had it last and reversed; that is treated as a one-off, not a
rule. Timber Place's missing distribution schedule is an absent optional source, not an
exception path.

**D-07 · Property records are emitted in `properties.yaml` order, which is source order.**
WayPointe: WayPointe AH LP first, 128 S. 5th Street West second. The published package reversed
them; soft target rule applies. P&L and Unit Availability are interleaved per record
(`for_each_record`), matching the published shape.

**D-08 · The repo holds the June 2026 golden bundle and nothing else; Drive holds live periods.**
No Git LFS, no history rewrite. The bundle is a test fixture and few-shot source. *Consequence:*
`data/bundle/2026-06/` is read-only after Phase 0; new periods never enter git.

**D-09 · Model: `claude-opus-5`, temperature 0, tool-forced structured output, 1-hour prompt cache.**
Cost is ~$5 per quarterly run at this volume; the Sonnet saving is not worth a decision. Pin a
dated snapshot when the API offers one and record it in every manifest. Batch API is not used
(complexity for ~$2.50/run).
*Amended 2026-09-26 (owner's decision, ahead of Opus 5's retirement):* the model is
`claude-opus-5-5`. It rejects forced tool use, so the tool is forced only on models known to
accept it and steered under `auto` + `strict` otherwise (A-16); everything else here stands.
Validated before the switch: three full evals at 100 % on every metric, and an eight-property
build page-for-page identical to the golden-label build (`docs/ANALYSIS-model-successor-2026-09.md`).
The Drive rehearsal could not run — the `2026-08` rehearsal tree had been deleted as planned. ~$3.73 per quarterly run, from ~$4.72.

**D-10 · Rendering with `pypdfium2` (Apache-2.0), composition with `pypdf`, OCR with `ocrmypdf`.**
PyMuPDF rejected on AGPL. 150 DPI, long edge ≤ 1568 px. OCR output *is* the composed source, so
McCathren packages ship searchable.

**D-11 · Every source page is placed, explicitly dropped, or a review reason. Never silently lost.**
Enforced as a build invariant with a test. This is the primary drift detector on a quarterly
cadence.

**D-12 · Review over guess.**
`unknown`, low confidence, footer disagreement, unmapped section, cardinality violation → the
package goes to `review/`, not `output/`, with a plain-language `REVIEW.md`. Exit code 2.

**D-13 · GitHub Actions is the fallback host and the first deployment; Azure Container Apps Job is the target.**
The job is minutes long, quarterly. Actions with repo secrets runs the identical container with
zero infrastructure and no new credentials. Azure is built (Bicep + workflow) but deployed only
when the user provides credentials (Phase 8 checkpoint).

**D-14 · Google Drive is the ingest and publish surface; layout mirrors the repo bundle.**
Service-account auth, single shared root folder. The runner never deletes or overwrites.

**D-15 · Build branch `build/v1`, one long-lived PR, commit per completed task.**
Cloud sessions can only push to their working branch. The user merges. If `gh pr merge` works
from a session, phases may be merged as they complete; otherwise stack on the branch. If the
environment refuses to push a branch named `build/v1` and insists on a session-scoped branch,
use that branch, record its name at the top of `PROGRESS.md` and in the PR, and treat every
reference to `build/v1` in these documents as that branch.

**D-16 · Python 3.12, `uv`, `ruff`, `mypy --strict` on `src/`, `pytest`, pydantic v2, Typer, structlog.**
No frameworks beyond these. No async unless a measured need appears.

---

*D-17 – D-24 were settled with the user on 2026-09-25/26 while designing continuous intake
(SPEC §18, PLAN Phase 10). They take effect when Phase 10 lands.*

**D-17 · Build each property as soon as its documents are ready; no fixed schedule. Supersedes
the quarterly cron of D-13 / SPEC §14.**
Documents can be ready on the 1st or the 24th, come from different people in any order, and can
be edited after a build; cadence is changing. *Consequence:* a stateless reconciler
(`crr reconcile`) runs every 30 minutes, derives everything from Drive, and builds a
property-month when its current files differ from its newest build. Push notifications and Logic
Apps were rejected (SPEC §18.11).

**D-18 · Release is out of scope. The `output/` folder is the whole review surface.**
The product builds packages for external review and delivery by people. The one requirement on
communication: a reviewer browsing a property's `output/` can see whether the newest report is
trustworthy and, if not, why. *Consequence:* no notifications, dashboards or messaging. A status
file whose *name* is the headline, plus a root summary. Supersedes the separate `review/` folder
of D-12; D-12's rule (review over guess) stands.

**D-19 · A folder per component declares what a file is. One file per component. Filenames are
never interpreted.**
Uploaders may be anyone with Drive access and no technical background. The model is never asked
which component a file is, and no content check second-guesses the folder: formats vary and
will change, so any such check is fragile (withdrawn 2026-09-26, SPEC §18.11). A wrong or
wrong-month document is built as given; the reviewer is the check.
*Consequence:* no `inputs/` folder; the exact-filename rule of SPEC §6.1 goes.

**D-20 · Only a change of input files triggers a build. Code and config changes do not;
`--force` (from the GitHub `Build a period` workflow) rebuilds on demand. Every build uses the
code current at the time it runs.**
Otherwise every merge to `main` would issue new versions of every open month.

**D-21 · When a component folder holds more than one PDF, the newest upload wins; the others are
renamed `SUPERSEDED - …`.**
"Upload time" is the head revision's time, which a rename does not change. The prefix is output,
never input: deleting the newest file makes the next-newest the winner and strips its prefix.
*Consequence:* the runner now renames files it did not write. It still never moves, overwrites
or deletes them (D-14).

**D-22 · Every build is a new version in the same `output/` folder. Old versions stay.**
`… - v<N>.pdf`, `… - v<N> - NEEDS REVIEW.pdf`.

**D-23 · A month is open until 42 days after its last day, then closed; later changes are
ignored and the status says so.**
The month is the one containing the source material; quarterly material goes in the quarter's
last month. The system creates the current and next month's folders for every property.

**D-24 · Only PDFs; spend is bounded by page count alone.**
A file must open as a PDF; nothing else about its content is checked (D-19). Spend is bounded by
a per-build cost ceiling (pages × a measured per-page rate), a three-strike failure cap and a
spend limit on the Anthropic workspace — none of which depends on a document's format.
An unrelated upload costs at most the ceiling, and the review gate usually flags it.

**D-25 · The folder also declares which property a file belongs to. A report filed under the
wrong property is built as that property's; nothing checks the name.**
Owner decision, 2026-09-29, after the production live test built Salmon Crossing's September
report from Bridgewater's owner report (finding F1). Managers name a property their own way
(`405 - Salmon Crossing - 2000 SW Salmon Ave Redmond, OR 97756`, `Timber Place by the Lake
(1000)`, `Lolo Peak Village LP`), scans garble names, and names change: a check that the pages
name the property would hold genuine reports and push stakeholders to change how they work. As
for a wrong or wrong-month document (D-19), the reviewer is the check; the right upload replaces
it with the next version. *Consequence:* no property-identity check. The one place a name is
matched is the Rent Manager schema's `Property:` line, which must split WayPointe's report
between its two records (SPEC §5 rule 3); as a side effect it also sends a Missoula report whose entity
name matches no configured record to review (`unresolved_record`) until `config/properties.yaml`
is updated.

**D-26 · The settle window is 30 minutes (was 60).**
Owner decision, 2026-09-29, after the production live test. A month is built by the first run
that starts 30 minutes after its last upload, so on the 30-minute schedule a report appears 30 to
60 minutes after the last file instead of 60 to 90. The cost of settling too early is a version
that the next upload supersedes, and the live test showed those are cheap and plain: a one-file
follow-up reuses every other label (about 2 cents), numbers continue, and the newest is marked
current. Thirty minutes still covers someone uploading several files one after another.
*Consequence:* `CRR_SETTLE_MINUTES` defaults to 30. Revisit after the first real month-end: every
version's index entry records its inputs' upload times, so how often a version was superseded
within the hour can be counted.
