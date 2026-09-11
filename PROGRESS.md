# Build progress

Single source of truth for build state. Claude Code ticks tasks here after each completes and
commits. Humans read this to see where things stand. Mirrors `docs/PLAN.md`; if they diverge,
PLAN.md defines the work and this file records what has been done.

**Branch:** `main` — v1 landed there via [#1](https://github.com/arcticbio/cornerstone.accounting.reports/pull/1) (built on the session branch `claude/gifted-lamport-wwgenm`; D-15 — every reference to `build/v1` in these documents means the release line, now `main`) · **Current phase:** 9 (complete) · **Tag:** `v1.0.0` pushed · **Last session note:** B-08 fixed; real-model eval run over all 172 pages and now **100 % on every metric**; the orientation defect it surfaced fixed — a page was shipping upside down — and the 59 % record score it reported traced to the metric, not the classifier. #7 merged to `main`; this branch merged it back cleanly. **B-09 is resolved: the production publish path works end to end.** **B-04 is resolved: Azure is
deployed, audited and armed**, a rehearsal period (`2026-08`) is seeded in Drive, and
`Actions → Run the Azure job` can start the job and put its arguments back. **B-11 is resolved
and PLAN Phase 8 is complete: the job ran on Azure and its logs show `crr 1.0.0`.** See "Pick up
here" below.

## Pick up here

_Last updated 2026-09-11 after a full audit of the plan, the documents and the live environment.
Everything below this block is the historical build record._

**State.** v1 is complete, merged to `main`, tagged `v1.0.0`. CI is green. The container is on
GHCR as `:build-v1`, republished by every push to `main`. The real model has built all eight
properties end to end.

**What the keyed runs established.**

| | |
|---|---|
| Full run | [34527782436](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34527782436) — 6 built, 2 to review, exit 2, 11m30s |
| Cost | **$4.72 per 8-property run, $0.59 per property** (172 calls) — the modelled ~$10 was over 2× high |
| Accuracy | every property resolved to its exact golden page count, the two review cases included; no `unknown`, no repair round, no retry, no refusal; confidence 0.95–0.98 across all 172 pages |
| Fixed on the way | **B-07** — the forced tool's schema carried `minimum`/`maximum`, which the live API rejects under `strict: true`. Invisible to every test, because a tool schema is only validated by the API. |
| Also fixed | CI's `BUILD_BRANCH` still named the pre-merge session branch, so merges to `main` rebuilt the image and silently did not push it |

**Open, in the order it is worth doing.**

1. ~~**B-08 — the two McCathren packages go to review on `cardinality_violation`.**~~
   **Fixed 2026-09-11, root-caused with a real-model run.** Not a labelling error: a re-run of
   Timber Place returned **23/23 correct labels**, continuations included. The split was the
   segmenter's. The model transcribed the `Property:` header on pages 20–23 of the seven-page
   General Ledger and not on 17–19, and SPEC §6.4 broke a run on any `record_qualifier` change —
   so `general_ledger` (`cardinality: one`) appeared twice. A qualifier only distinguishes
   instances of a `per_record` section; on a one-cardinality section §5 rule 1 discards it
   anyway. The break condition is now qualified, SPEC §6.4 amended, three tests pin both
   directions. **Both properties rebuilt against the real model: `ok`, 25 and 29 pages, exit 0**
   ($1.63 for the pair).
2. ~~**`crr eval --classifier anthropic`**~~ — **run 2026-09-11, locally, now that B-01 is
   closed.** All 31 documents, 172 pages: **page accuracy 1.0000, continuation 1.0000, boundary
   F1 1.0000**, gate passed, **$4.66** (`20260910T233821Z`). It found one real defect and one
   false alarm, and both are now closed — **every metric reads 100 %**:
   - ~~**orientation 0.00 % (0/1)**~~ — **fixed 2026-09-11.** Not a metric artefact: the
     classifier named Timber Place p3 `rotated_90_cw` where the truth is `rotated_90_ccw`, the
     composer applied 270° instead of 90°, and **the page shipped to investors upside down**.
     Every gate passed — both rotations give the same 792×612 landscape page — so only this
     metric saw it. Two prompt rewrites made it *worse* (1/4 → 0/4 → 0/6) and were reverted.
     Orientation is now a cross-check of two independent signals with a discrimination arbiter
     on disagreement (SPEC §7.6, A-09). Timber Place rebuilt clean, page verified right-side-up,
     eval orientation now **100 % (1/1)**.
   - ~~**Missoula `record_qualifier` 59.38 % (38/64)**~~ — **a reporting defect, not a
     classifier one; fixed 2026-09-11 and now 100.00 % (64/64)** (`20260910T235640Z`, $1.97).
     Nothing in the pipeline changed — no label, no plan, no output page. The metric compared
     the string the model printed instead of the record the page lands in, and it did it
     twice over. Run down with real labels rather than inferred:
     - Rent Manager prints the `Property:` header on every section-head page and the model
       transcribes it, while golden carries `null` on a single-record property because
       `map_qualifier` maps null *and* the matching `pm_name` to the same record. Checked page
       by page on Fort Grounds: **0 of 16 pages resolve differently**. That was 38 → 62.
     - The last 2 were WayPointe pages 4 and 7 — `unit_availability` *continuations* where the
       model correctly returned `null`, exactly as the prompt requires, and the metric scored
       each page in isolation without the §6.4 inheritance the segmenter applies. Scoring the
       effective qualifier makes it 64/64.
     Both real-model label sets are committed as fixtures under `tests/data/`, so the metric is
     pinned against actual model output rather than a hand-written stub (A-10).
3. ~~**`crr eval` does not persist per-page predictions.**~~ **Done 2026-09-11.** Both metric
   defects above had to be re-measured with fresh keyed runs ($4.66 + $1.97) on labels that had
   not changed. `crr eval` now writes `<report stem>.predictions.json` beside every report, and
   `crr eval --from <file>` re-scores it under the current metrics with no model calls.
   Verified over the full corpus: the replayed report is **identical to the live one across all
   31 documents and 172 pages, in 1.8 s**. `evidence` is omitted from the file — it is a
   model-written sentence about the page and these files are committed — and the run's token
   usage is carried so a replay still reports what the run cost.
4. **A dispatchable eval workflow.** The eval now runs locally, but CI still runs only the
   golden one; there is no way to trigger a keyed eval from Actions. A `command` input on
   `build-period.yml`, or a small `eval.yml`, is the cheap way in.
5. ~~**Log `is_continuation` on `classify.page`**~~ — done; a run log now answers the B-08
   question without the artifact.
6. ~~**B-09 — no package can reach Drive.**~~ **RESOLVED 2026-09-11 — one has.** The shared
   drive is live, the runner is Content manager on it, the 2026-06 and 2026-09 skeletons are
   built out (43 folders, all owned by the *drive*), and a real `--repo gdrive` build of Fort
   Grounds published `Fort Grounds - Investor Report - June 2026.pdf` into `output/` — verified
   by downloading it back: 8 pages, 6 bookmarks, correct title. **The production publish path
   works.** Original text: *(Not this branch's work; it arrived with #7, and it
   is the top production blocker.)* The service account has no storage quota, so every
   `--repo gdrive` upload fails `403 storageQuotaExceeded` — including `publish`, which means a
   gdrive build classifies, composes, and then fails at the last step. Folders are exempt, so
   the setup looks healthy right up until the first byte. Needs an account change, not a code
   change: move the Drive root into a **shared drive** with the runner as **Content manager** —
   written up as **[`docs/SETUP-GOOGLE-DRIVE.md`](docs/SETUP-GOOGLE-DRIVE.md)** (2026-09-11),
   verifiable with `crr preflight --repo gdrive`. `--repo local` is unaffected.
   **Mitigated, not fixed, 2026-09-11:** a build now proves the repository is writable before it
   constructs a classifier, so the run stops in about a second instead of spending ~$4.72 and
   failing at the last stage. Confirmed against the live account. See B-09 in `QUESTIONS.md`.
7. ~~**Two open PRs, neither redundant.**~~ **Settled 2026-09-11.** The operator merged
   [#7](https://github.com/arcticbio/cornerstone.accounting.reports/pull/7) at 01:33 and `main`
   merged back into this branch **with no conflicts** — the two had shared history (#7 branched
   off this branch at `a3deab3`), not the independent implementations this file predicted. The
   mis-call, and the one-command check that would have caught it, are recorded as B-10.
8. ~~**B-04 — Azure.**~~ **Deployed and audited 2026-09-11.** The operator ran the bootstrap and
   the deploy workflow; runs 3–7 of *Deploy to Azure* succeeded, the latest at 03:48 from
   `main`@`020fc7d`. Confirmed from the run logs, not assumed:
   - subscription `e7eadf09…`, resource group `rg-cust-cornerstone`, job `crr-quarterly`,
     environment `crr-env`, workspace `crr-logs`, vault `crr-kv-accounting`;
   - the job's identity (`e3de70d7…`) already reads the vault — the grant step reported
     "nothing to do", so step 6's warning path is not outstanding;
   - GHCR pull credentials are supplied, so the private package is reachable;
   - `scheduleEnabled=true`; cron `0 6 20 1,4,7,10 *`; **next unattended fire 20 Oct 06:00 UTC**;
   - the what-if diff for run 7 shows `~ value: "1_tUMelVG8…" => "1SQUgfGiw1…"` — Azure took the
     new **shared-drive** root folder id, which is what makes B-09's fix reach the job.
   `:build-v1` was republished by the merges of #8 and #9, so the tag the job pulls now contains
   the publish preflight.
9. **A rehearsal period is seeded in Drive: `2026-08`, 31 files, all eight properties.** The
   job's baked arguments are `build --repo gdrive --classifier anthropic` with **no `--period`**,
   and the runner defaults to the month just ended — which is `2026-08` today. Without inputs
   under that label a no-argument start (the schedule's exact shape) would have found nothing.
   The files are the June bundle placed under an August label: **a rehearsal dataset, not a
   deliverable.** Delete the `2026-08` tree before anyone could mistake its output for a real
   quarter.
10. **`Actions → Run the Azure job` (`.github/workflows/azure-job.yml`) starts the job from
    GitHub.** This session cannot: there is no `az` CLI in the container and no `AZURE_*`
    credential, so the one thing it could not do was press the button. The workflow does the
    `job update --args` → `job start` → wait → logs → **restore** sequence from `SETUP-AZURE.md`
    step 7, with the restore as an `always()` step so a cancelled or failed run still leaves the
    quarterly cron armed with the right arguments. It reads the arguments to restore out of
    `infra/main.bicep` rather than off the live job, so a job left mutated by an earlier manual
    start gets corrected instead of preserved.
12. **Drive is tidied, and the setup documents no longer point at the dead root.** Trashed on
    2026-09-11: the B-09 test package under Fort Grounds / 2026-06 June in the shared drive (four
    inputs and the whole `output/`, six files), and the 29 abandoned, empty folders in the old
    My Drive root. Trash rather than permanent delete — reversible for 30 days, and in a shared
    drive a Content manager may only trash anyway. The shared drive now holds the skeleton plus
    the 31 rehearsal files and nothing else; `preflight` still passes and `2026-08` still reads
    8/8 ready. **The find that mattered:** `SETUP-CREDENTIALS.md`, `SETUP-AZURE-PORTAL.md` (twice)
    and `infra/README.md` all still gave the *old My Drive* folder id as the value to configure —
    so anyone following them would have rebuilt B-09 exactly. All four now give the shared-drive
    id and say why it has to be a shared drive. The old root folder itself is left in place,
    empty.
13. **PLAN Phase 8's acceptance is met in full — *job exists, manual start succeeds, logs show
    `crr version`*.** Third run, 2026-09-11 07:27 UTC
    ([34574240440](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34574240440)),
    execution `crr-quarterly-94admd0`, replica `…-2zqvz`:

    ```
    Successfully Connected to container: 'crr'
    2026-09-11T07:25:32.278441982Z crr 1.0.0
    ```

    The whole cycle is proven end to end: set the arguments → start → wait → read the container's
    logs → restore by re-deploying the template → **re-read the job and confirm** (`The job is
    holding: crr build --repo gdrive --classifier anthropic`). The first execution was
    `crr-quarterly-8gkaig4` at 06:19 UTC
    ([34569379705](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34569379705)),
    and it took three runs to get here because of three defects, all in the workflow, all mine,
    all fixed (**A-13**):
    - `az containerapp job logs show --job-execution-name` is not a flag. It is `--execution` —
      and `--tail` is capped at 300, which cost a second run's logs. Both were found by the
      `--help` dump the step now performs on failure; the second took one run rather than
      another guess because of it.
    - **`az containerapp job update --args` cannot set a multi-token argument list at all** —
      the CLI reads `--repo` as one of its own flags. So the restore failed and the job was left
      holding `version`, which the 20 October cron would have run to no effect. Repaired within
      the hour by a deploy; the what-if diff is the proof (`- 0: "version"` → `+ 0: "build" …`).
      The workflow now takes a `choice`, not free text, and restores by *calling* `deploy.yml`
      as a reusable workflow, with a third job that re-reads the job and compares it to the
      template.
11. ~~**B-01's remaining half**~~ — **closed 2026-09-11.** The session container strips
    `ANTHROPIC_API_KEY`, but not `CRR_ANTHROPIC_API_KEY`; `settings.py` now reads either name.
    The fix existed on the abandoned branch `claude/ecstatic-goodall-ji7yur` (PR #2) and had never
    reached `main`, which is why this was recorded as impossible. `pytest -m api` runs in-session:
    **5 passed**. A local `crr eval --classifier anthropic` is now possible too.

**Traps worth knowing.** ~~`ocrmypdf` is broken in the Claude Code container, so 10 OCR invariant
tests fail locally and pass in CI.~~ **Fixed 2026-09-11:** apt installs `ocrmypdf` for CPython 3.12
while `/usr/bin/python3` is 3.11, so it died importing PIL; `scripts/session_start.sh` now repoints
its shebang, and the full invariant suite passes locally — **60 passed**. Still true: the `2026-09`
Drive skeleton already exists (folders only), so a real September run writes into it.

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
| 2026-09-10 | post-v1 | `v1.0.0` pushed by the user; CI green on the final tree; version bumped 0.1.0 → 1.0.0; Azure + credentials setup docs written | Azure bootstrap (user), then B-01/B-04 |
| 2026-09-10 | post-v1 | PR #1 merged to `main`; first keyed run dispatched (`2026-06`/`fort-grounds`/`local`/`anthropic`) — the key works, the tool schema does not (B-07); fix on `claude/wonderful-wright-scuu96` | Republish the image, re-dispatch |
| 2026-09-10 | post-v1 | B-07 fixed and merged (PR #3); CI now publishes the image from `main`; re-run green — `fort-grounds` built, 8/8 pages match golden, **$0.56** | Full 8-property keyed run; `crr eval --classifier anthropic` |
| 2026-09-10 | post-v1 | Full 8-property keyed run: 6 built, 2 to review (`cardinality_violation`, both McCathren); every property hit its golden page count; **$4.72/run, $0.59/property** | Work the two review cases; `crr eval --classifier anthropic` |
| 2026-09-11 | post-v1 | Full audit of plan, documents and live environment. **B-04 closed** — Azure deployed, identity reads the vault, GHCR pull credentials present, shared-drive folder id taken, cron armed. Rehearsal period `2026-08` seeded in Drive (31 files, 8/8 ready). `azure-job.yml` added so a session can start the job and the arguments always get restored (B-11). | Dispatch `Run the Azure job` with `version`, then `validate-config`, then the no-argument build |
| 2026-09-11 | post-v1 | **Phase 8 complete.** `crr version` ran on Azure and its logs say `crr 1.0.0` (`crr-quarterly-94admd0`). Took three runs: `--job-execution-name` is not a flag, `--args` cannot set a multi-token list (the restore left the cron on `version` — repaired), `--tail` is capped at 300. The restore is now a call to `deploy.yml` with a verification job after it (A-13). | `validate-config`, then the `build` option against the seeded `2026-08` data (~$4.72) |

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
- [x] ~~**Blocked (B-01):** smoke run needs `ANTHROPIC_API_KEY`.~~ **Unblocked and done 2026-09-11.** B-01 is closed, so `pytest -m api` runs in-session (**5 passed**), and the real model has since classified the whole corpus rather than one document: 172 pages across all 31 documents at confidence 0.95–0.98, no `unknown`, no repair round, no retry, no refusal. Fort Grounds' PM source specifically is committed as a real-model fixture (`tests/data/fort-grounds-real-model-labels.json`).

**Acceptance:** Golden classifier round-trips 100 % of golden pages (`tests/eval/test_golden_plans.py` builds every plan from it). ~~The real-model smoke run and the ≥ 95 % / cache-read assertions are blocked on B-01.~~ **Met 2026-09-11** once B-01 closed: the `api` tests run (5 passed, cache read included) and the real model scores 100 % page accuracy over all 172 pages, well above the 95 % threshold. Gate: ruff, `mypy src`, 206 passed + 5 skipped (the `api` tests) at the time; **447 passed** today.

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
- [x] ~~**Blocked (B-01):** needs `ANTHROPIC_API_KEY`.~~ **Run 2026-09-11.** `crr eval --classifier anthropic` over all 31 documents / 172 pages: page accuracy 1.0000, continuation 1.0000, boundary F1 1.0000, gate passed, **$4.66**. The two sub-100 % metrics it first reported are both closed — one a real defect (A-09, a page shipping upside down), one a reporting defect (A-10) — and every metric now reads 100 %.
- [x] ~~**Blocked (B-01):** the golden-build manifests are the comparison baseline.~~ **Compared 2026-09-11.** The full 8-property keyed build ([run 34527782436](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34527782436)) resolved **every property to its exact golden page count**, the two review cases included; both McCathren properties then rebuilt to `ok` at 25 and 29 pages after B-08.

**Acceptance:** Golden eval report committed (`eval/reports/LATEST.md`): **100 % page accuracy, 100 % continuation, 100 % record, 100 % orientation, boundary F1 1.0000** over all 31 documents / 172 pages, every manager above both thresholds. ~~The real-model eval and build are blocked on B-01.~~ **Both run 2026-09-11:** the keyed eval reads 100 % on every metric ($4.66) and the keyed build produced all eight packages ($4.72, $0.59/property).

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
- [x] ~~**Gated (B-04):** needs `AZURE_CREDENTIALS` and a subscription / resource group.~~ **Deployed 2026-09-11.** The operator ran the bootstrap and the deploy workflow; *Deploy to Azure* runs 3–7 succeeded, the latest from `main`@`020fc7d`. `crr-quarterly` is live in `rg-cust-cornerstone`, its identity reads `crr-kv-accounting`, GHCR pull credentials are supplied, the shared-drive root folder id is in place, and the quarterly cron is armed (next fire 20 Oct 06:00 UTC). See B-04 in `QUESTIONS.md` for the audited details. **Smoke-run 2026-09-11:** `crr version` → execution `crr-quarterly-94admd0`, `Succeeded`, logs show `crr 1.0.0`.
- [x] `.github/workflows/azure-job.yml` (`Actions → Run the Azure job`): sets `--args` on the job, starts it, waits, prints the execution's logs, and **restores the scheduled arguments in an `always()` step** — because `--args` cannot be passed to `job start`, so a manual run has to mutate the definition the quarterly cron reads, and a cancelled run would otherwise leave the schedule pointed at `version`. Restores from `infra/main.bicep`, not from the live job, so an already-mutated job is corrected rather than preserved (B-11).

**Acceptance:** **Bicep compiles in CI** (`az bicep build`, credential-free `bicep` job, green in run 34462978204). The template, its README and the deploy workflow are also held by 10 structural tests. ~~Deployment itself is gated (B-04).~~ **Met in full 2026-09-11** — B-04 and B-11 both resolved. The job exists, a manual start succeeds, and the logs show `crr 1.0.0` (execution `crr-quarterly-94admd0`, [run 34574240440](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34574240440)). **Phase 8 is complete.**

## Phase 9 — Hardening, docs, second-period readiness

- [x] `docs/RUNBOOK.md` (332 lines): the quarterly checklist, preparing a period in Drive, running from Actions in screenshots-in-words, a failure-mode table covering all eight review codes plus every hard failure and what to do about each, adding a property, adding a manager, changing a prompt, and the model-deprecation procedure.
- [x] `page_count_drift` wired end to end. `LocalFsRepository` scans `work/` for an earlier period's manifest; `GoogleDriveRepository` reads the newest published `build-manifest.json` from a prior period. The pipeline asks whichever repository it has, and a history lookup that fails never fails a build. Tested with a hand-placed prior manifest: 16 pages → 3 pages fires the rule, and no history fires nothing.
- [x] `crr build` prints input / cache-read / cache-write / output tokens, API calls and the USD estimate, per run and per property; every manifest already carried `cost`.
- [x] `tests/unit/test_logging_hygiene.py` runs a real build with structlog captured and asserts no page text, no tenant name, no path, no PDF or PNG bytes and no secret appears in any record — while confirming sha256s *are* logged. **It caught one leak:** `repository.published` logged the output filename, which carries the property's public name. Both repositories now log the artefact's shape, not its name.
- [x] `README.md`: what the system is and why it is shaped this way, a five-line quickstart, the exit-code contract, and a map of the repository.
- [x] See "v1.0.0 summary" at the foot of this file.
- [x] Tag `v1.0.0` — created here, **pushed by the user** (this session's credentials are scoped to its branch and the remote refused the tag ref). The package version was `0.1.0` at tag time and has since been bumped to `1.0.0`, so `crr version` and every manifest's `runner_version` match the tag.

**Acceptance:** `README.md` → `docs/RUNBOOK.md` takes someone who has never seen the repository from "the exports arrived" to "the packages are in Drive", including what to do with a review outcome. The `v1.0.0` tag is the last task.


## Eval results (append newest first)

| Date | Classifier | Model | Prompt | Overall | Missoula | McCathren | Cobalt | Cost/run | Report |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-10 | anthropic | `claude-opus-5` | v1 | 6/8 built, 2 to review | 4/4 built | 0/2 built (both `cardinality_violation`) | 2/2 built | **$4.72** (8 properties) | [run 34527782436](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34527782436) |
| 2026-09-10 | anthropic | `claude-opus-5` | v1 | — | fort-grounds only: 8/8 output pages, 19/19 pages 0.96–0.98 | — | — | $0.56 (1 property) | [run 34526230410](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34526230410) |
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
| CI | **green on the final tree `943e664`** — runs [34464245438](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34464245438) and [34464250151](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34464250151), all three jobs |
| Invariants | all six of SPEC §9, over the eight real builds |

### Cost per run

**Measured 2026-09-10, all eight properties.** Dispatch
[34527782436](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34527782436)
— `2026-06`, every property, `local` / `anthropic`, on `claude-opus-5`. Exit code 2: six built,
two to review. 11m30s wall clock.

| | |
|---|---|
| API calls | 172 — one per page, as designed |
| Tokens | input 694,361 · cache read 601,254 · cache write 7,193 · output 35,086 |
| **Measured** | **$4.72 per full run — $0.59 per property** |

| Property | Status | Pages | Golden | |
|---|---|---|---|---|
| fort-grounds | built | 8 | 8 | ✅ |
| lolo-peak-village | built | 8 | 8 | ✅ |
| mullan-crossing | built | 8 | 8 | ✅ |
| waypointe | built | 10 | 10 | ✅ |
| timber-place | **needs_review** | 25 | 25 | `cardinality_violation` |
| river-falls | **needs_review** | 29 | 29 | `cardinality_violation` |
| bridgewater | built | 24 | 24 | ✅ |
| salmon-crossing | built | 18 | 18 | ✅ |

Every property resolved to its golden page count, the two review cases included. No page was
classified `unknown`, no repair round fired, no retry, no refusal; page confidence ran 0.95–0.98
across all 172. Timber Place p3 — the sideways Financial Aged Receivable — came back
`aged_receivable` at 0.96.

**The two review cases are the review gate doing its job, not a failure.** Both are McCathren,
both OCR'd, and both trip the same rule: `segment.done` counted 12 runs across 11 section ids on
Timber Place (11 across 10 on River Falls), so one `cardinality: one` section was split into two
runs — a page that continues a section was labelled as starting a new one. The resolver still
placed every page correctly, which is why the page counts match; the gate refused to publish on
a segmentation it could not prove (D-12). **Which section and which page is not in the run log**
— `is_continuation` is not logged per page — it is in each package's `REVIEW.md` inside the
[manifests artifact](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34527782436).
Worth noting the golden classifier builds both of these cleanly, so this is a real
model-vs-golden difference on the two scanned properties, and `crr eval --classifier anthropic`
is what would quantify it.

The earlier single-property measurement, kept for the cache comparison — dispatch
[34526230410](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34526230410)
— `2026-06` / `fort-grounds` / `local` / `anthropic`, against `:build-v1` on `claude-opus-5`:

| | |
|---|---|
| API calls | 19 (16 PM pages + 3 Cornerstone pages) |
| Tokens | input 74,791 · cache read 62,089 · cache write 5,857 · output 3,887 |
| **Measured** | **$0.56 for Fort Grounds** |
| Outcome | `built`, 8 pages, 6 bookmarks, 6 sections dropped, nothing sent to review |
| Accuracy | all 8 composed pages match `eval/golden/missoula/fort-grounds.json`; 19/19 pages classified at confidence 0.96–0.98 |

Fort Grounds is one of the smaller properties (19 pages against 172 across all eight), and it
paid its own cache writes with nothing to read them back, so **$0.56 × 8 is the wrong
extrapolation in both directions**. What it does settle is that the modelled ~$1.30 per property
below was roughly 2× high. A full eight-property run measures the real number.

The superseded model, from the token shapes the code sends and the built-in price table:

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
| **B-01** | `ANTHROPIC_API_KEY` does not reach the session container → the real-model smoke run, eval and build are unrun. A **new session** picks the variable up; see `docs/SETUP-CREDENTIALS.md`. |
| **B-04** | Azure: the user has chosen to proceed. `docs/SETUP-AZURE.md` + `infra/bootstrap.sh` are the walkthrough; the bootstrap needs their `az login`. |
| A-01 … A-07 | Seven assumptions taken where the spec was silent or wrong, each recorded in `QUESTIONS.md` and amended into `SPEC.md` in the same commit. The three worth a second look: `temperature` cannot be sent to this model family (A-02), exemplar images cannot live in the system prompt (A-03), and the local repository publishes under `work/published` so a build never writes into the read-only bundle (A-06). |

### What the second period will test

The June bundle is one period of evidence. Three things are rules on one observation and could
turn out to be habits: the Missoula drop list, WayPointe's two-record shape, and Timber Place's
missing distribution schedule. All three are config, and all three surface as review reasons
rather than silent behaviour if they change.
