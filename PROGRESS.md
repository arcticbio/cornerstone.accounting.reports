# Build progress

Single source of truth for build state. Claude Code ticks tasks here after each completes and
commits. Humans read this to see where things stand. Mirrors `docs/PLAN.md`; if they diverge,
PLAN.md defines the work and this file records what has been done.

**Branch:** `claude/gifted-lamport-wwgenm` (session-scoped branch; D-15 — every reference to `build/v1` in these documents means this branch) · **PR:** [#1](https://github.com/arcticbio/cornerstone.accounting.reports/pull/1) · **Current phase:** 9 (complete) · **Last session note:** _(none yet)_

## Session log

| Date (UTC) | Phase | What happened | Next |
|---|---|---|---|
| — | — | Handoff package committed; build not started | Phase 0, task 1 |
| 2026-09-10 | 0 | Bundle moved to `data/bundle/2026-06`, `.DS_Store` purged, bundle verified | Phase 0, scaffold |
| 2026-09-10 | 0 | Scaffold, settings, CLI, CI, PR #1 opened | Phase 1 |
| 2026-09-10 | 1 | Models, render/text/OCR/inspect, 31-document sweep, McCathren labels visually verified | Phase 2 |
| 2026-09-10 | 2 | Config validation, address grammar, segmenter, resolver; `expected_output` frozen for all 8 | Phase 3 |
| 2026-09-10 | 3 | Classifier protocol, golden classifier, footer check, prompts, Anthropic classifier, `crr classify` | Phase 4 |
| 2026-09-10 | 4 | Composer, manifest, review gate, local repository, pipeline, `crr build`; 8/8 golden builds | Phase 5 |
| 2026-09-10 | 5 | Eval harness, metrics, markdown report, gate; golden eval 100 % | Phase 6 (real-model eval blocked on B-01) |
| 2026-09-10 | 6 | Drive repository, fake-Drive tests, live tests green, 2026-09 skeleton created | Phase 7 |
| 2026-09-10 | 7 | Dockerfile, CI image job, GHCR publish, build-period workflow, runbook | Phase 8 (tasks 1-3) |
| 2026-09-10 | 8 | Bicep, infra README, deploy workflow; deploy step gated on credentials | Phase 9 |
| 2026-09-10 | 9 | Drift rule, cost report, logging hygiene (one leak found and fixed), runbook, README, tag | v1.0.0 |

## Phase 0 — Repository hygiene and scaffold

- [x] `git mv "Report Assembly Bundle" data/bundle/2026-06`. Removed 5 `.DS_Store` files from git and disk; shipped `.gitignore` already covers Python, `work/`, `.env`, `.DS_Store` — unchanged.
- [x] Bundle verified — see "Bundle verification" at the foot of this file. All checks pass.
- [x] `pyproject.toml` written with all listed deps; `uv lock` → 68 packages; hatchling build backend, `crr` console script. `extend-exclude = ["*.md", "data"]` on ruff because ruff ≥ 0.16 reformats python fences inside markdown and `docs/SPEC.md` is prose.
- [x] `src/crr/__init__.py`, `cli.py` (`version`, stub `validate-config`, stub `eval`), `settings.py` per SPEC §12, `log.py` (structlog → JSON on stderr). `uv run crr version` prints `crr 0.1.0`.
- [x] `scripts/session_start.sh` run by hand: exit 0, `uv sync: ok`. It reports `ocrmypdf:` with a traceback in this container — see "Environment notes" below; tesseract 5.3.4 and gs 10.02.1 are fine.
- [x] `.github/workflows/ci.yml`: apt OCR toolchain, `uv sync --frozen`, ruff check + format, `mypy src`, pytest with coverage, `crr validate-config`, `crr eval --classifier golden --gate` (both stubs for now).
- [x] Confirmed present: `docs/` (SPEC, PLAN, DECISIONS, QUESTIONS, 2 × ANALYSIS), `config/` (`properties.yaml`, 4 schemas, 3 output definitions), `eval/golden/` (8 property label files + README). `crr validate-config` loads all 8 YAML files.
- [x] PR opened: [#1 Cornerstone Report Runner v1](https://github.com/arcticbio/cornerstone.accounting.reports/pull/1) with the phase table in the description.

**Acceptance:** `uv run crr version` → `crr 0.1.0`. **CI green on PR #1** — run
[34462978204](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34462978204),
all three jobs.

### Environment notes (this container)

- `/usr/bin/python3` is a locally built 3.11 while Debian's `ocrmypdf` entry point targets the
  distribution's 3.12, so `ocrmypdf --version` fails with `ImportError: cannot import name
  '_imaging' from 'PIL'`. Run under 3.12 it is **ocrmypdf 15.2.0**. A one-line shim was dropped in
  the git-ignored `.venv/bin/ocrmypdf` so `uv run` finds a working entry point; CI and the Docker
  image install `ocrmypdf` from apt and use the stock one. Nothing in `src/` depends on the shim.
- tesseract 5.3.4, ghostscript 10.02.1, `uv` 0.8.17.
- `ANTHROPIC_API_KEY` is **not set** → Phase 3/5 real-model work degrades to the golden classifier.
- `GOOGLE_SERVICE_ACCOUNT_B64` and `CRR_GDRIVE_ROOT_FOLDER_ID` are set → Phase 6 can run for real.

## Phase 1 — Document model, rendering, text, OCR

- [x] `models/domain.py` per SPEC §3 — frozen, `extra="forbid"`; `Orientation.correcting_rotation` encodes the SPEC §6.5 rotation table; `ResolvedSection` validates page contiguity and that `orientation_fixes` stay inside the section.
- [x] `preprocess/render.py`: pypdfium2 → RGB PNG, 150 DPI, long edge capped at 1568 px, cached by (sha256, page, dpi, max_edge); a re-run reuses the cache without re-rasterising.
- [x] `preprocess/text.py`: pypdf text per page, capped at 6 000 chars. Normalisation collapses *horizontal* whitespace and drops blank lines but keeps line breaks — the footer check (SPEC §7.4) reads the report name off the last line, so flattening newlines would cost it its anchor. Probe: ≥ 40 non-whitespace chars on ≥ 90 % of pages.
- [x] `preprocess/ocr.py`: subprocess wrapper with the spec'd argv, version capture, `/Rotate` diffing to report whether `--rotate-pages` changed anything, `OcrError` with the apt install hint when the binary is missing, and stderr path-redaction so property names never reach a log. `ocr_if_needed()` skips when the document already has text or the output definition disables OCR.
- [x] `crr inspect <pdf>` (`--json` for machine output): sha256, page count, text-layer verdict, per-page size / `/Rotate` / effective size / char count / footer line.
- [x] All 31 documents inspected: page counts equal the golden labels for every one, `has_text_layer` false for exactly the two McCathren PM baselines and true for the other 29. Locked in as `tests/eval/test_bundle_documents.py` (32 tests, 4.3 s).
- [x] Both McCathren sources OCR'd with ocrmypdf 15.2.0 into `work/2026-06/<property>/ocr/` (~45 s each). Text layer now true for both, and **no page falls below the 40-character bar** (Timber Place 23/23, River Falls 26/26). **`--rotate-pages` changed nothing on either document** — including Timber Place page 3, the sideways Financial Aged Receivable. So the first-pass rotation is a no-op here and the classifier's orientation label is the only thing that will land that page upright (SPEC §6.2, §6.5).
- [x] Contact sheets rendered to `work/contact-sheets/{timber-place,river-falls}.png` (6 per row, numbered) and every page checked against its golden label. **All 49 section / continuation / record labels are correct** — no section was mislabelled. One addition: Timber Place p3 now carries `"orientation": "rotated_90_ccw"` (content reads bottom-to-top up the left edge; tesseract OSD independently reports `Rotate: 90`). Verification notes written into both golden files' `notes`.
- [x] Unit tests on reportlab fixtures: long-edge cap (and that a small page is *not* upscaled), aspect-ratio preservation, render cache hits and DPI-keyed misses, probe threshold at exactly 90 % of pages and 40 non-whitespace chars, OCR argv, rotation detection, missing-binary and failure paths incl. path redaction, and both OCR-skip conditions.

**Acceptance:** `crr inspect` matches golden page counts for all 31 documents (`tests/eval/test_bundle_documents.py`, 32 passed). McCathren golden labels visually verified against contact sheets; the single correction (Timber Place p3 orientation) is recorded in the golden file's `notes`. Gate green: ruff, `mypy src`, 62 tests.

## Phase 2 — Config loading, validation, address grammar, resolver

- [x] `config/` loaders with full SPEC §4 validation. `crr validate-config` is real: it collects *every* problem across all three formats into one report rather than stopping at the first. Two shipped-config fields were absent from the SPEC §4.1 table (`fingerprint.ocr_quality_note`, integer `typical_pages`) — both documentation; SPEC amended to match the config as shipped.
- [x] `resolve/address.py`: hand-written parser; 28 tests covering every production and 15 distinct error messages, each naming the production that failed.
- [x] `resolve/resolver.py`: `for_each_record`, `pm:*` in source order minus drops, `#n` occurrence, per-record expansion in `properties.yaml` order, optional flow items and optional sources, bookmark rendering (with the single-record ` - {record_name}` suffix dropped), autorotate transforms, and `unaccounted_pages` — the D-11 evidence that no page is silently lost.
- [x] `segment/`: run-length grouping with qualifier inheritance on continuation pages, `unknown` isolation, cardinality checks, and `record_qualifier` → record id mapping (SPEC §5 rule 3). All five required cases tested, plus the mapping rules.
- [x] `expected_output` generated for all 8 properties, reviewed by hand against SPEC §1 and D-03/D-06/D-07, and frozen into the golden files. Every property resolves to exactly its `expected_output_page_count` with **zero review reasons and zero unaccounted pages**. `tests/eval/test_golden_plans.py` (37 tests) now pins it, including the D-06 front-matter rule (WayPointe included — the published package put its block last, we do not), D-07 record order, the Missoula drop list, and the Timber Place `rotate:90`.

**Acceptance:** `crr validate-config` passes on the shipped config and fails on each of the six SPEC §9.6 bad cases (`tests/unit/fixtures/bad-config/`, one broken thing per tree). Resolver test green for all 8 properties. Gate: ruff, `mypy src`, 170 tests.

**Hand review of `expected_output` (the record worth keeping):** Missoula properties emit front
matter + P&L Comparison + Unit Availability + Owner Statement and drop the other six reports,
matching `ANALYSIS-assembly-rules` and D-03 — the unsourced Rent Manager Balance Sheet is not
recreated. WayPointe emits WayPointe AH LP before 128 S. 5th (D-07, the reverse of the published
package) and its Cornerstone block leads (D-06, also the reverse of the published package).
Timber Place has two front-matter pages, its absent distribution schedule handled as an optional
source rather than an exception. Cobalt and McCathren pass through every PM page in source order.

## Phase 3 — Classifier

- [x] `classify/protocol.py` (`Classifier` protocol, `PageInput`, `Usage`) and `classify/golden_classifier.py`. The golden classifier renders each label's *record id* back to the record's `pm_name`, so the segmenter's qualifier→record mapping is exercised on every golden build rather than bypassed.
- [x] `classify/footer_check.py`. Verified on real bundle text: it names the right section on **16/16** Missoula pages (report name leads the matched footer line) and **12/12** Cobalt report pages (report name is the line *above* the `Created on …` match). Cobalt's nine owner-statement pages correctly yield no verdict — that section declares no `footer_label`, and `Page N of M` names no report. Disagreement is recorded, never applied (D-05).
- [x] `classify/prompts/<schema_id>/v1.md` for all four schemas over a shared `_shared/` body, so one manager's prompt can be revised and its `prompt_version` bumped without touching the others. Exemplar selection honours `exclude_same_property` (which is what keeps an eval from scoring the model against its own answer key) and caps at two pages per section.
- [x] `classify/anthropic_classifier.py`. Three corrections to SPEC §7.2, all recorded in `QUESTIONS.md` and amended in the spec: `temperature` is rejected on this model family (A-02 — determinism now comes from the forced tool's closed enum plus `strict: true`, with `output_config.effort=low`); the API's `system` field takes text blocks only, so exemplar images lead the *user* turn with their own 1-hour cache breakpoint (A-03); and a `stop_reason: "refusal"` is handled as `unknown` → review rather than retried into a guess (A-04). 16 unit tests against a fake client cover argv, both cached prefixes, previous-page carry-over, the repair round, retries and cost.
- [x] `crr classify <pdf> --schema <id> [--classifier golden --property <id>] [--out json]`. Prints section, continuation, confidence, the footer verdict and its agreement marker, and the record qualifier.
- [x] `tests/integration/test_classify_api.py` (marker `api`): page 1 of Fort Grounds, WayPointe, Timber Place and Bridgewater, plus a cache-read assertion on page 2. Skipped in this environment — no `ANTHROPIC_API_KEY` (B-01).
- [ ] **Blocked (B-01):** smoke run needs `ANTHROPIC_API_KEY`. Run `uv run crr classify "data/bundle/2026-06/Missoula Property Management/Fort Grounds/2026-06 June/inputs/05 PM Source - Missoula PM Baseline.pdf" --schema rentmanager-missoula` once the key is set.

**Acceptance:** Golden classifier round-trips 100 % of golden pages (`tests/eval/test_golden_plans.py` builds every plan from it). The real-model smoke run and the ≥ 95 % / cache-read assertions are blocked on B-01. Gate: ruff, `mypy src`, 206 passed + 5 skipped (the `api` tests).

## Phase 4 — Composer, manifest, review gate, end-to-end with golden labels

- [x] `compose/composer.py`: plan-order page copying across documents, `/Rotate` fixes with the mediabox preserved, one outline entry per section at its first page, `/Title`/`/Producer`/`/CreationDate` metadata, and the spec'd filename. Deterministic — two runs are byte-identical apart from `/CreationDate`.
- [x] `manifest/`: the SPEC §10 model, a canonical writer, and `schema.json` generated from the model and committed (a test fails if they drift).
- [x] `review/`: all eight reason codes, ordered by severity then position, and a `REVIEW.md` that explains each finding in plain language, groups repeats, and says what to do next.
- [x] `repository/local_fs.py`: period discovery, input fetch with a missing PM source as a hard failure and a missing Cornerstone component simply absent, and publishing that never overwrites (`… (build 2).pdf`). **Publishes under `CRR_PUBLISH_ROOT` (default `<work_dir>/published`) rather than beside the inputs** — the local root is the June bundle, which is a read-only fixture (A-06).
- [x] `pipeline.py` runs fetch → preprocess → classify → segment → resolve → plan → compose → manifest → review → publish, writing every artefact under `work/<period>/<property>/`. Data problems become review reasons; only exceptions become `FAILED`, and even then the manifest is written. `crr build` exits 0/2/1 per SPEC §6.8. OCR output is content-addressed and cached, so a rebuild never re-OCRs unchanged bytes.
- [x] All 8 built. Every assertion holds: status `BUILT`, plan equals `expected_output` page for page, PDF page count equals plan length, no review reasons, one bookmark per section (6/6/6/8/13/13/8/8), `/Title` set, McCathren PM pages carry a text layer on **every** page with `ocr_applied` recorded, and Timber Place's aged-receivable page comes out 792×612 effective. Manifests committed to `eval/reports/golden-build-2026-06/`.
- [x] `tests/eval/test_invariants.py` — all six, over the eight real builds. §9.1 reconciles *every* input page against plan ∪ dropped ∪ reasons per document; §9.3 additionally spies on every `PdfReader` the composer opens; §9.4 compares two builds byte for byte with `/CreationDate` masked.
- [x] `tests/unit/test_pipeline_negative.py` on synthetic PDFs: unknown page, missing required section, unmapped section, low confidence → `NEEDS_REVIEW` (published to `review/` with `REVIEW.md`); missing PM source → `FAILED` with a manifest written and nothing published; and a second publish lands as `(build 2)`.

**Acceptance:** All eight golden builds `BUILT`; the six invariants green; coverage **95 %** on `src/crr` (target 85 %). Full gate: ruff, `mypy src`, 299 passed + 5 skipped (the `api` tests) in 2 m 50 s.

## Phase 5 — Eval harness and the real model

- [x] `crr eval [--classifier golden|anthropic] [--pm <id>] [--property <id>] [--gate] [--report <path>]`. Scores page accuracy, continuation, `record_qualifier` (Missoula only), orientation (only where a golden page carries the key), section-boundary F1 after segmentation, confusion pairs, tokens and USD. Writes a timestamped markdown report plus `eval/reports/LATEST.md`.
- [x] CI runs `crr eval --classifier golden --gate` (wired in Phase 0, real since this commit). The golden run skips OCR and rasterising — the golden classifier opens neither — so the self-consistency check takes **5 s** instead of 92.
- [ ] **Blocked (B-01):** needs `ANTHROPIC_API_KEY`. Command is ready: `uv run crr eval --classifier anthropic --gate`.
- [ ] **Blocked (B-01):** needs `ANTHROPIC_API_KEY`. The golden-build manifests in `eval/reports/golden-build-2026-06/` are the comparison baseline, and `tests/eval/test_invariants.py` already pins the expected page sequences.

**Acceptance:** Golden eval report committed (`eval/reports/LATEST.md`): **100 % page accuracy, 100 % continuation, 100 % record, 100 % orientation, boundary F1 1.0000** over all 31 documents / 172 pages, every manager above both thresholds. The real-model eval and build are blocked on B-01.

## Phase 6 — Google Drive repository

- [x] `repository/drive_client.py` (the whole Drive API surface, and the seam the fake replaces — `supportsAllDrives`/`includeItemsFromAllDrives` live in one place) and `repository/google_drive.py`: folder-name navigation with per-object caching, a case-insensitive fallback that warns, downloads that skip a file already local at the same size, uploads that never overwrite (`… (build N).pdf`), and `ensure_period_skeleton` for preparing a period.
- [x] `--repo gdrive` on `crr build`; `crr inspect --repo <local|gdrive> --period X` lists each property as `ready` / `NOT READY` with the missing roles named and optional ones marked. Verified live against the real Drive root.
- [x] 17 unit tests against an in-memory Drive that records every call, so "never deleted" and "never overwrote" are assertions rather than hopes. 3 live tests (marker `gdrive`) **pass against the real Drive**: the root is reachable, every folder in it is one a manager claims, and listing any period never raises.
- [x] `docs/RUNBOOK.md` → "Preparing a period in Drive": the layout, the byte-for-byte folder and file names per manager, how to create the folders (by hand or with the one-liner), what "ready to build" means, and the service-account sharing the runner needs.
- [x] Credentials are present and work. The Drive root was **empty**; the `2026-09 September` skeleton now exists for all eight properties (folders only, no files) — see "Drive folder ids" below. `crr inspect --repo gdrive --period 2026-09` reports 0/8 ready, which is correct: the folders are waiting for inputs.

**Acceptance:** Fake-Drive tests green (17); the live integration tests green (3) against the real root folder `1_tUMelVG8trnjPmJWul0YXo23VgWgdSc`.

### Drive folder ids (created 2026-09-10, folders only)

Root: `1_tUMelVG8trnjPmJWul0YXo23VgWgdSc`

| Path | Folder id |
|---|---|
| `Missoula Property Management` | `185uRadvslOjSoUoxSgYdICuSkRzaleOK` |
| `Missoula Property Management/Fort Grounds/2026-09 September/inputs` | `15u50Mq7WRO0UcMNKcxeNBktYeeKN3u2k` |
| `Missoula Property Management/Lolo Peak Village/2026-09 September/inputs` | `1l557KSfVsDg6576YhNfFmziJgBOVEQ9E` |
| `Missoula Property Management/Mullan Crossing/2026-09 September/inputs` | `1H5ea-P7dqQonpIAtPTHjG8nUgkaAku1b` |
| `Missoula Property Management/WayPointe/2026-09 September/inputs` | `1RjTXrLjthOWoGqHehGABrB1Q2WlO3hOi` |
| `McCathren Management and Real Estate Services` | `1qZfzgkFiD32oT_tx8gYd89U_ZwWsUrgQ` |
| `McCathren Management and Real Estate Services/Timber Place/2026-09 September/inputs` | `1RF73MvSaypeF9xmoYlU3FP6j4r_f7ciJ` |
| `McCathren Management and Real Estate Services/River Falls/2026-09 September/inputs` | `102T5WgQsNLRolVJuxvIfK10QsVlGrcr2` |
| `Cobalt Properties Group` | `13QftbvQOz3BNa-NjySa-UMzyeHli_vmf` |
| `Cobalt Properties Group/Bridgewater/2026-09 September/inputs` | `1Czjxm0WDLmRoOMV1Vn3K-xOWDlziY6rb` |
| `Cobalt Properties Group/Salmon Crossing/2026-09 September/inputs` | `1yVvGMmWkV1gzG2R1HBrn7SPKJ7BFRMVY` |

**The service account must be shared into the root folder as Editor** for a build to publish.
It reads and writes nothing outside that folder.

## Phase 7 — Container and GitHub Actions runner

- [x] `Dockerfile`: multi-stage on `python:3.12-slim`, deps layer cached separately from source, OCR toolchain (including `tesseract-ocr-osd`, which `--rotate-pages` needs and whose absence only bites on the scanned documents that need it most), non-root `crr` user, `crr version` healthcheck, `/work` volume. `.dockerignore` keeps `data/`, `work/` and `eval/reports/` out of the build context.
- [x] CI `image` job: builds the image, runs `crr version`, **asserts `/app/data` does not exist** in the image, checks all three OCR binaries inside it, then runs the golden build with the checkout mounted read-only. Not yet executed — see B-02/B-03.
- [x] GHCR publishing with `packages: write` on the build branch (D-15: the session branch is treated as `build/v1`) and on `v*` tags; `build-period.yml` pulls with `packages: read` and `docker login`.
- [x] `.github/workflows/build-period.yml`: all five dispatch inputs (`classifier` added alongside the four required, so a dry run against the bundle needs no code change), the quarterly cron present but commented, secrets and vars wired, manifests and `REVIEW.md` uploaded `if: always()`, and the SPEC §6.8 exit codes interpreted — 0 quiet, 2 a warning annotation, anything else fails the job.
- [x] `docs/RUNBOOK.md` → "Running a build from GitHub Actions": where to click, what each input does, how to read a green/yellow/red result, where the manifests artifact is, how to work the review queue (including that a config fix — not a PDF edit — is the remedy), and which secrets and variables must exist.

**Acceptance:** **Met.** CI run [34462978204](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34462978204):
the image builds (44 s), `crr version` runs, `/app/data` is proved absent, tesseract / ocrmypdf /
ghostscript all answer *inside* the container, the golden build runs end to end in it (77 s,
OCR included), and the image is pushed to GHCR as `:build-v1` and `:sha-<short>`.
`build-period.yml` is dispatchable. Also held by 17 structural tests.

## Phase 8 — Azure Container Apps Job (deploy step gated)

- [x] `infra/main.bicep`: Log Analytics (90-day retention), Container Apps Environment, and a Container Apps Job with the quarterly cron, 2 vCPU / 4 GiB, `replicaTimeout: 3600`, `replicaRetryLimit: 1`, a system-assigned identity, and both secrets **referenced** from an existing Key Vault — the template creates no vault and holds no secret value. `scheduleEnabled=false` parks the cron on 31 February when you want the job without the schedule.
- [x] `infra/README.md`: what gets deployed, the vault-and-secrets prerequisites, the one deploy command, the **role assignment the job's identity needs after the first deploy** (it cannot exist before the job does), manual starts including the credential-free `version` / `validate-config` smoke runs, log commands, how exit code 2 shows up as a failed execution in Azure, and how to update or park the schedule.
- [x] `.github/workflows/deploy.yml`: compiles the template *before* signing in, then what-if, then deploy — and **`what_if_only` defaults to true**, so a mis-click previews rather than deploys. CI compiles the template on every push in a credential-free `bicep` job.
- [ ] **Gated (B-04):** needs `AZURE_CREDENTIALS` and a subscription / resource group, or an explicit "Actions is enough for now". This is the Phase 7 checkpoint question.

**Acceptance:** **Bicep compiles in CI** (`az bicep build`, credential-free `bicep` job, green in run 34462978204). The template, its README and the deploy workflow are also held by 10 structural tests. Deployment itself is gated (B-04).

## Phase 9 — Hardening, docs, second-period readiness

- [x] `docs/RUNBOOK.md` (332 lines): the quarterly checklist, preparing a period in Drive, running from Actions in screenshots-in-words, a failure-mode table covering all eight review codes plus every hard failure and what to do about each, adding a property, adding a manager, changing a prompt, and the model-deprecation procedure.
- [x] `page_count_drift` wired end to end. `LocalFsRepository` scans `work/` for an earlier period's manifest; `GoogleDriveRepository` reads the newest published `build-manifest.json` from a prior period. The pipeline asks whichever repository it has, and a history lookup that fails never fails a build. Tested with a hand-placed prior manifest: 16 pages → 3 pages fires the rule, and no history fires nothing.
- [x] `crr build` prints input / cache-read / cache-write / output tokens, API calls and the USD estimate, per run and per property; every manifest already carried `cost`.
- [x] `tests/unit/test_logging_hygiene.py` runs a real build with structlog captured and asserts no page text, no tenant name, no path, no PDF or PNG bytes and no secret appears in any record — while confirming sha256s *are* logged. **It caught one leak:** `repository.published` logged the output filename, which carries the property's public name. Both repositories now log the artefact's shape, not its name.
- [x] `README.md`: what the system is and why it is shaped this way, a five-line quickstart, the exit-code contract, and a map of the repository.
- [x] See "v1.0.0 summary" at the foot of this file.
- [x] Tag `v1.0.0` created (annotated, on `c34c69b`) — **but not pushed**: this session's credentials are scoped to its branch and the remote refuses a tag ref with `HTTP 403`. Push it after merging: `git tag -a v1.0.0 <merge commit> -m "Cornerstone Report Runner v1.0.0" && git push origin v1.0.0`. The tag message is reproduced in B-05.

**Acceptance:** `README.md` → `docs/RUNBOOK.md` takes someone who has never seen the repository from "the exports arrived" to "the packages are in Drive", including what to do with a review outcome. The `v1.0.0` tag is the last task.


## Eval results (append newest first)

| Date | Classifier | Model | Prompt | Overall | Missoula | McCathren | Cobalt | Cost/run | Report |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-10 | golden | — | — | 1.0000 | 1.0000 | 1.0000 | 1.0000 | $0.00 | [LATEST](eval/reports/LATEST.md) |

## Bundle verification (Phase 0)

Checked 2026-09-10 against `config/properties.yaml`.

- PM folder names on disk are byte-equal to the three `folder` values in `config/properties.yaml`:
  `Cobalt Properties Group`, `McCathren Management and Real Estate Services`,
  `Missoula Property Management`.
- 8 property folders, each with exactly one `2026-06 June/` period folder containing
  `inputs/`, `target/` (1 file), `reference/` (1 file) and `build-spec.json`.

| Property | Manager | `inputs/` files |
|---|---|---|
| fort-grounds | missoula | 4 |
| lolo-peak-village | missoula | 4 |
| mullan-crossing | missoula | 4 |
| waypointe | missoula | 4 |
| timber-place | mccathren | 3 (no `03 Cornerstone - Investor Distribution Schedule.pdf`) |
| river-falls | mccathren | 4 |
| bridgewater | cobalt | 4 |
| salmon-crossing | cobalt | 4 |

- Input filenames match `pm_source_filename` / `cornerstone_files` in `config/properties.yaml` exactly.
- Bundle root retains `README.md`, `BUILD-RULES.md`, `index.json` from the earlier analysis, as instructed.
- 5 `.DS_Store` files removed from the index and the working tree.


---

## v1.0.0 summary

### What was built

`crr` assembles the eight quarterly investor packages from two upstream sources. A vision model
labels every page of every input — section, continuation, property record, orientation,
confidence, one sentence of evidence — and nothing else in the system is a judgement call: the
page plan is resolved from a per-manager output definition, composed with `pypdf`, and recorded
in a manifest that names every source sha256, every label, every dropped page and the exact
config version that produced it (D-01).

| Layer | What it is |
|---|---|
| `config/` | 4 source schemas, 3 output definitions, the property registry. **A new property or a new manager is a config change, not a code change** (D-02). |
| `preprocess/` | text-layer probe, `ocrmypdf` (cached by content hash), `pypdfium2` rendering capped at 1568 px |
| `classify/` | the Anthropic classifier (forced tool, closed enum, two 1-hour cached prefixes), the golden classifier, and the footer check that cross-examines both |
| `segment/` · `resolve/` | run-length segmentation, the address grammar, flow resolution, and the `unaccounted_pages` set that proves no page was silently lost (D-11) |
| `compose/` · `manifest/` · `review/` | deterministic composition, the audit record, and the gate that sends an ambiguous package to review rather than to investors (D-12) |
| `repository/` | local disk and Google Drive, neither of which ever deletes or overwrites |
| `evaluate/` | page, continuation, record, orientation and boundary-F1 scoring with a committed markdown report and a CI gate |

Hosting: one container image, published to GHCR, run today by GitHub Actions and ready for the
Azure Container Apps Job in `infra/`.

### Numbers

| | |
|---|---|
| Golden builds | **8/8 `BUILT`**, page-for-page equal to the frozen `expected_output` |
| Eval (golden classifier) | page accuracy **1.0000**, continuation **1.0000**, record **1.0000**, orientation **1.0000**, boundary F1 **1.0000** over 31 documents / 172 pages |
| Eval (real model) | **not yet run** — no `ANTHROPIC_API_KEY` in this environment (B-01) |
| Tests | **375 passed, 5 skipped** (the `api` tests), 94 % coverage on `src/crr` |
| CI | green on all three jobs at `1beaf40`; on the final tree the `image` job completed every step (in-container golden build 101 s, GHCR push) before the run was cancelled by the next push. See B-06; **confirm the last run goes green before merging.** |
| Invariants | all six of SPEC §9, over the eight real builds |

### Cost per run

**Not yet measured** — that needs one keyed run (B-01), after which every manifest records it
exactly. The modelled estimate, from the token shapes the code actually sends and the built-in
price table:

| | |
|---|---|
| API calls | 172 (one per page of every input document) |
| Input tokens | ~0.55 M uncached (page image + page text) |
| Cache reads | ~4.4 M (the per-document prefix, read on every page after the first) |
| Cache writes | ~0.49 M (the prefix, written once per document) |
| Output tokens | ~0.016 M |
| **Estimate** | **~$10 per full 8-property run**, ~$1.30 per property, on `claude-opus-5` at list price |

Higher than the ~$5 D-09 anticipated, and the reason is the exemplar images: up to two per
section per document is a large cached prefix. If the real number matters, the first lever is
`MAX_EXEMPLARS_PER_SECTION`, and `crr eval` will say what accuracy it costs.

### Open items

| | |
|---|---|
| **B-01** | `ANTHROPIC_API_KEY` unset → the real-model smoke run, eval and build are unrun. Everything else is built and tested against a fake client. |
| **B-04** | Azure deployment gated on `AZURE_CREDENTIALS`, or on a decision that Actions is enough. This is the Phase 7 checkpoint. |
| A-01 … A-07 | Seven assumptions taken where the spec was silent or wrong, each recorded in `QUESTIONS.md` and amended into `SPEC.md` in the same commit. The three worth a second look: `temperature` cannot be sent to this model family (A-02), exemplar images cannot live in the system prompt (A-03), and the local repository publishes under `work/published` so a build never writes into the read-only bundle (A-06). |

### What the second period will test

The June bundle is one period of evidence. Three things are rules on one observation and could
turn out to be habits: the Missoula drop list, WayPointe's two-record shape, and Timber Place's
missing distribution schedule. All three are config, and all three surface as review reasons
rather than silent behaviour if they change.
