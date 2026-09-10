# Build progress

Single source of truth for build state. Claude Code ticks tasks here after each completes and
commits. Humans read this to see where things stand. Mirrors `docs/PLAN.md`; if they diverge,
PLAN.md defines the work and this file records what has been done.

**Branch:** `claude/ecstatic-goodall-ji7yur` (session-scoped branch per D-15; every `build/v1` reference means this branch) · **PR:** _(link after Phase 0)_ · **Current phase:** 0 · **Last session note:** _(none yet)_

## Session log

| Date (UTC) | Phase | What happened | Next |
|---|---|---|---|
| — | — | Handoff package committed; build not started | Phase 0, task 1 |
| 2026-09-10 | 0 | Classifier key renamed to `CRR_ANTHROPIC_API_KEY` (the unprefixed name is reserved by Claude Code on the web and stripped from the container); added `docs/SETUP-CREDENTIALS.md`. No build tasks started. | Phase 0, task 1 |

## Phase 0 — Repository hygiene and scaffold

- [ ] `git mv "Report Assembly Bundle" data/bundle/2026-06`. Remove every `.DS_Store` from git. Verify the shipped `.gitignore` covers Python, `work/`, `.env`, `.DS_Store`.
- [ ] Verify the bundle: the three PM folder names are byte-equal to `folder` in `config/properties.yaml`; 8 property folders, each with `inputs/` (4 files, 3 for Timber Place), `target/`, `reference/`, `build-spec.json`. The bundle root also carries its own `README.md`, `BUILD-RULES.md`, `index.json` from the earlier analysis — leave them. Record counts in `PROGRESS.md`.
- [ ] `pyproject.toml` (`crr` package, Python 3.12, deps: pydantic, pydantic-settings, typer, structlog, pyyaml, pypdf, pypdfium2, pillow, anthropic, jinja2, google-api-python-client, google-auth; dev: pytest, pytest-cov, ruff, mypy, reportlab, types-PyYAML). `uv lock`.
- [ ] `src/crr/__init__.py`, `cli.py` with `crr version`, `settings.py` per SPEC §12.
- [ ] Verify the shipped `.claude/settings.json` SessionStart hook and `scripts/session_start.sh` work once `pyproject.toml` exists (run the script by hand; it must exit 0).
- [ ] `.github/workflows/ci.yml`: ruff, mypy, pytest with coverage, `crr validate-config`, `crr eval --classifier golden --gate`. Python 3.12, `uv`. Until Phase 5, `crr eval` may be a stub that exits 0 and prints "eval not implemented"; `validate-config` may be a stub that only loads the YAML.
- [ ] Copy `docs/ANALYSIS-*.md` from the handoff (already present). Confirm `docs/`, `config/`, `eval/golden/` are in place and `crr validate-config` is wired (may be a stub that loads YAML).
- [ ] Open PR `build/v1 → main` titled "Cornerstone Report Runner v1" with a phase table in the description.

**Acceptance:** _(record evidence here when met)_

## Phase 1 — Document model, rendering, text, OCR

- [ ] `models/` per SPEC §3.
- [ ] `preprocess/render.py`: pypdfium2 → PNG per page, 150 DPI, long edge ≤ 1568. Cache by (sha256, page, dpi).
- [ ] `preprocess/text.py`: pypdf text per page, normalised; text-layer probe per SPEC §6.2.
- [ ] `preprocess/ocr.py`: ocrmypdf wrapper (subprocess), `--skip-text --rotate-pages --optimize 1`; version capture; graceful error if tesseract absent.
- [ ] `crr inspect <pdf>` command.
- [ ] Run `crr inspect` over all 8 PM sources + 23 Cornerstone files; assert page counts equal the golden files; assert `has_text_layer` is false for both McCathren sources and true for all others. Record in `PROGRESS.md`.
- [ ] OCR both McCathren sources into `work/`; confirm text now extracts on every page; note Timber Place page 3 orientation after `--rotate-pages`.
- [ ] **Visual verification of golden labels for McCathren**: render contact sheets (`work/contact-sheets/<property>.png`, 6 pages per row with page numbers) and check each page's golden label against what the image shows. Correct `eval/golden/mccathren/*.json` if anything is wrong and note the correction. (The labels were derived by page offset from the published packages; two spot checks passed. This is the full check.)
- [ ] Unit tests with reportlab-generated fixtures: rendering size cap, text probe threshold, OCR skip when text exists (mock subprocess).

**Acceptance:** _(record evidence here when met)_

## Phase 2 — Config loading, validation, address grammar, resolver

- [ ] `config/` loaders for schemas, outputs, properties with full validation per SPEC §4. `crr validate-config` real.
- [ ] `resolve/address.py`: parser for the grammar in SPEC §5 with tests for every production and every error.
- [ ] `resolve/resolver.py`: `ResolvedSection[] + OutputDefinition + Property → PlanItem[]`, including `for_each_record`, `pm:*` expansion, `drop`, optional handling, bookmark rendering.
- [ ] `segment/`: run-length grouping + cardinality validation per SPEC §6.4, with tests for: continuation break, record change, back-to-back same section, `unknown` isolation, blank continuation page.
- [ ] Tests that build `ResolvedSection`s straight from `eval/golden/*.json` and assert the resolved plan matches the golden `expected_output` for all 8 properties (this tests resolver + output definitions without any PDF I/O). **Note:** `expected_output` is not yet in the golden files — generate it here from the output definitions, review it by hand against SPEC §1 / DECISIONS D-03/D-06/D-07, then commit it into the golden JSON as the fixed expectation.

**Acceptance:** _(record evidence here when met)_

## Phase 3 — Classifier

- [ ] `classify/protocol.py`, `classify/golden_classifier.py`.
- [ ] `classify/footer_check.py` per SPEC §7.4 with tests on real page text from the bundle (Missoula and Cobalt).
- [ ] `classify/prompts/<schema>/v1.md` Jinja2 templates per SPEC §7.2. Exemplar selection per `exemplar_policy`.
- [ ] `classify/anthropic_classifier.py`: message construction with cache_control, forced tool, retries, token accounting, pydantic parsing with one repair retry.
- [ ] `crr classify <pdf> --schema <id>` command printing a table and writing JSON.
- [ ] Integration test (marker `api`): classify page 1 of each of the 4 PM sources (one per manager + WayPointe) and assert the expected section id. Skips without key.
- [ ] Smoke run: `crr classify` on Fort Grounds PM source with the real model; eyeball against golden; record accuracy and token counts in `PROGRESS.md`.

**Acceptance:** _(record evidence here when met)_

## Phase 4 — Composer, manifest, review gate, end-to-end with golden labels

- [ ] `compose/`: pypdf composer per SPEC §6.6 incl. rotation, bookmarks, metadata, filename.
- [ ] `manifest/`: model, writer, generated JSON schema committed.
- [ ] `review/`: rules per SPEC §6.8; `REVIEW.md` renderer.
- [ ] `repository/local_fs.py` per SPEC §6.1.
- [ ] `pipeline.py` orchestrating one property; `crr build` command with `--classifier golden`.
- [ ] Run `crr build --period 2026-06 --classifier golden` for all 8. Assert status BUILT, page sequence equals `expected_output`, bookmarks present (one per section), McCathren outputs have a text layer on every page, and the Timber Place aged-receivable output page has effective landscape dimensions (792×612 after `/Rotate`). Commit the 8 manifests to `eval/reports/golden-build-2026-06/` (manifests only, not PDFs).
- [ ] Invariant tests per SPEC §9 (all six).
- [ ] Negative tests: an `unknown` page → NEEDS_REVIEW; a missing required section → NEEDS_REVIEW; a section in neither flow nor drop → NEEDS_REVIEW; missing PM source → FAILED.

**Acceptance:** _(record evidence here when met)_

## Phase 5 — Eval harness and the real model

- [ ] `crr eval` per SPEC §8 with golden and anthropic classifiers; markdown report; `--gate`.
- [ ] CI runs `crr eval --classifier golden --gate`.
- [ ] Run `crr eval --classifier anthropic` over all 31 golden documents. Commit the report. If any manager is below threshold: analyse the confusion pairs, revise that schema's `visual_cues`/`description` or the prompt (bump `prompt_version`), re-run, commit both. Up to three iterations; then record the residual and continue.
- [ ] Run `crr build --period 2026-06 --classifier anthropic` for all 8. Compare each manifest's plan to the golden build's plan; assert identical page sequences. Commit manifests to `eval/reports/anthropic-build-2026-06/`.

**Acceptance:** _(record evidence here when met)_

## Phase 6 — Google Drive repository

- [ ] `repository/google_drive.py` per SPEC §6.1 and §13. Service account from `GOOGLE_SERVICE_ACCOUNT_B64`. Folder-name navigation with caching; downloads; uploads; never delete/overwrite.
- [ ] `--repo gdrive` on `crr build`; `crr inspect --repo gdrive --period X` lists what is present per property.
- [ ] Unit tests with a fake Drive service (in-memory tree). Integration test (marker `gdrive`) that lists the root folder; skipped without credentials.
- [ ] `docs/RUNBOOK.md` section: "Preparing a period in Drive" — the exact folder/file names, what "ready" means.
- [ ] If credentials are present: create the folder skeleton for `2026-09 September` under the root (folders only, no files) so the user can see the expected layout, and record the folder ids.

**Acceptance:** _(record evidence here when met)_

## Phase 7 — Container and GitHub Actions runner

- [ ] `Dockerfile` per SPEC §14; multi-stage; non-root user; `crr version` healthcheck.
- [ ] CI job that builds the image and runs `crr build --classifier golden --repo local` inside it with the checkout mounted (`-v $PWD/data:/data -e CRR_BUNDLE_ROOT=/data/bundle/2026-06`) — proves tesseract/ocrmypdf/ghostscript are present and OCR works in-container. The image itself must not contain `data/bundle/` (SPEC §14, §16).
- [ ] Publish image to GHCR: `:build-v1` and `:sha-<short>` on every push to `build/v1`; `:latest` and `:vX.Y.Z` on tags `v*`. Workflows that pull need `packages: read` and `docker login ghcr.io`.
- [ ] `.github/workflows/build-period.yml`: `workflow_dispatch` with `period` (required), `property` (optional), `repo` (`gdrive` default, `local` for testing), `image_tag` (default `build-v1`); optional cron commented with the quarterly schedule; runs the GHCR image with secrets `CRR_ANTHROPIC_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_B64`, vars `CRR_GDRIVE_ROOT_FOLDER_ID`; uploads `work/` manifests as an artifact; fails the job on exit 1, marks a warning annotation on exit 2.
- [ ] `docs/RUNBOOK.md`: "Running a build from GitHub Actions" with screenshots-in-words.

**Acceptance:** _(record evidence here when met)_

## Phase 8 — Azure Container Apps Job (deploy step gated)

- [ ] `infra/main.bicep`: resource group-scoped: Log Analytics, Container Apps Environment, Key Vault (secrets referenced, not created), Container Apps Job (schedule trigger `0 6 20 1,4,7,10 *` UTC, manual trigger allowed, image from GHCR, env from Key Vault refs, 2 vCPU / 4 GiB, replica timeout 3600, retry 1).
- [ ] `infra/README.md`: one-command deploy with `az deployment group create`; how to set the two Key Vault secrets; how to `az containerapp job start`.
- [ ] `.github/workflows/deploy.yml`: `workflow_dispatch`, uses `AZURE_CREDENTIALS`, `az bicep build`, what-if, deploy.
- [ ] **Gated on `AZURE_CREDENTIALS` + subscription/resource group:** deploy, then start the job once with args `version` then `validate-config` (a smoke run that needs neither Drive nor the bundle), capture logs to `PROGRESS.md`.

**Acceptance:** _(record evidence here when met)_

## Phase 9 — Hardening, docs, second-period readiness

- [ ] `docs/RUNBOOK.md` complete: quarterly checklist (place inputs → dispatch → check status → review queue handling → where outputs land), failure modes and fixes, how to add a property, how to add a manager (schema + output + golden labels + eval), how to change a prompt (eval before merge), model deprecation procedure.
- [ ] `page_count_drift` review rule wired (needs "last manifest" lookup in the repository; local: scan `work/`; Drive: read previous period's manifest).
- [ ] Cost report: `crr build` prints tokens and USD estimate; manifest carries it.
- [ ] Structured logging review: no page text, no image bytes, no secrets in any log line (test with a log capture fixture).
- [ ] README.md at repo root: what this is, 5-line quickstart, links to SPEC/PLAN/RUNBOOK.
- [ ] Final `PROGRESS.md` summary: what was built, eval numbers, cost per run, open items.
- [ ] Tag `v1.0.0`.

**Acceptance:** _(record evidence here when met)_


## Eval results (append newest first)

| Date | Classifier | Model | Prompt | Overall | Missoula | McCathren | Cobalt | Cost/run | Report |
|---|---|---|---|---|---|---|---|---|---|

## Bundle verification (Phase 0)

_(counts go here)_
