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
