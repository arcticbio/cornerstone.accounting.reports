# Build progress

Single source of truth for build state. Claude Code ticks tasks here after each completes and
commits. Humans read this to see where things stand. Mirrors `docs/PLAN.md`; if they diverge,
PLAN.md defines the work and this file records what has been done.

**Continuous intake (Phase 10) is built, audited, fixed and live-tested; its release to `main` is a PR from `claude/gracious-davinci-nnkdv1`** — see "Pick up here", item 0.

**Branch:** `main` — v1 landed there via [#1](https://github.com/arcticbio/cornerstone.accounting.reports/pull/1) (built on the session branch `claude/gifted-lamport-wwgenm`; D-15 — every reference to `build/v1` in these documents means the release line, now `main`) · **Current phase:** 9 (complete) · **Tag:** `v1.0.0` pushed · **Last session note:** B-08 fixed; real-model eval run over all 172 pages and now **100 % on every metric**; the orientation defect it surfaced fixed — a page was shipping upside down — and the 59 % record score it reported traced to the metric, not the classifier. #7 merged to `main`; this branch merged it back cleanly. **B-09 is resolved: the production publish path works end to end.** **B-04 is resolved: Azure is
deployed, audited and armed**, a rehearsal period (`2026-08`) is seeded in Drive, and
`Actions → Run the Azure job` can start the job and put its arguments back. **B-11 is resolved
and PLAN Phase 8 is complete: the job ran on Azure and its logs show `crr 1.0.0`.** See "Pick up
here" below.

## The production host has run a full quarter, clean

**2026-09-11 08:16 UTC · execution `crr-quarterly-ectvlit` · exit 0 · $4.78**
([run 34576554024](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34576554024))

The Azure Container Apps Job classified, composed and published **all eight properties** against
the seeded `2026-08` period, with the real model, writing into the shared drive. **Nothing went
to review.** This is the first run of the system that has ever exited 0 — the previous full keyed
run was 6 built / 2 to review.

Verified by downloading every published PDF back out of Drive and opening it, rather than by
believing the runner's own log:

| Property | Pages | Golden | Bookmarks | Status |
|---|---:|---:|---:|---|
| bridgewater | 24 | 24 | 8 | built |
| fort-grounds | 8 | 8 | 6 | built |
| lolo-peak-village | 8 | 8 | 6 | built |
| mullan-crossing | 8 | 8 | 6 | built |
| river-falls | 29 | 29 | 13 | built |
| salmon-crossing | 18 | 18 | 8 | built |
| timber-place | 25 | 25 | 13 | built |
| waypointe | 10 | 10 | 8 | built |

**Every page count matches golden exactly**, every `/Title` is correct, 0 review reasons, 8
`output/` folders and 0 `review/` folders in Drive. 172 API calls, `$4.78` ($0.60 per property) —
within a cent of the $4.72 the Actions host measured, so the cost model holds on Azure too.

Two things this confirms that only a real run could. **B-08 is fixed in production**: Timber
Place and River Falls, the two McCathren properties that used to fail `cardinality_violation`,
both built clean at their exact golden page counts. And the `build` option mutates nothing — the
workflow's "Set the arguments" step was **skipped** and the restore and confirm jobs did not run,
because the job already holds the arguments the cron reads.

~~⚠️ These eight packages say August and contain June figures. Delete the `2026-08` tree.~~
**Done** — the `2026-08` rehearsal tree was deleted before 2026-09-26.

## Pick up here

_Last updated 2026-09-11 after a full audit of the plan, the documents and the live environment.
Everything below this block is the historical build record._

**State.** v1 is complete, merged to `main`, tagged `v1.0.0`. CI is green. The container is on
GHCR as `:build-v1`, republished by every push to `main`. The real model has built all eight
properties end to end.

**Model successor readiness (2026-09-25, branch `claude/gracious-dirac-t7w39j`).** The
classifier now runs on `claude-opus-5-5`, which rejects the forced tool call v1 relies on
(A-16). **The default is now `claude-opus-5-5`** (D-09 amended). Three full evals at 100 % on
every metric ($3.63–3.72 against $4.67), and all eight properties built end to end page-for-page
identical to the golden-label build ($3.73). See `docs/ANALYSIS-model-successor-2026-09.md`.

**What the keyed runs established.**

| | |
|---|---|
| Full run | [34527782436](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34527782436) — 6 built, 2 to review, exit 2, 11m30s |
| Cost | **$4.72 per 8-property run, $0.59 per property** (172 calls) — the modelled ~$10 was over 2× high |
| Accuracy | every property resolved to its exact golden page count, the two review cases included; no `unknown`, no repair round, no retry, no refusal; confidence 0.95–0.98 across all 172 pages |
| Fixed on the way | **B-07** — the forced tool's schema carried `minimum`/`maximum`, which the live API rejects under `strict: true`. Invisible to every test, because a tool schema is only validated by the API. |
| Also fixed | CI's `BUILD_BRANCH` still named the pre-merge session branch, so merges to `main` rebuilt the image and silently did not push it |

**Open, in the order it is worth doing.**

0. **Phase 10 — continuous intake is built and rehearsed on the live drive; it stops at its
   STOP** (2026-09-26, branch `claude/eager-fermat-h7ub70`, not yet merged). `crr reconcile`: a
   folder per component, newest upload wins, a new version per change of input files, versions
   side by side in `output/`, a status file whose name is the headline. SPEC §18, D-17 – D-24,
   PLAN Phase 10. **What is left is the operator's:** merge; deploy (the job then runs
   `reconcile`, still on the quarterly cron); measure one no-op run on Azure (A-15); then arm
   the 30-minute cron — one line in `infra/main.bicep` (RUNBOOK → *Running it on Azure*).
   The rehearsal's Fort Grounds / 2026-09 v1–v6 moved out of the production root on 2026-09-28
   into a separate rehearsal root; September is clean in production (Audit follow-ups, item 3).
   **Audited 2026-09-26, fixed 2026-09-28, live-tested 2026-09-29** (Phase 10 → *Audit
   follow-ups* and *Live test* below). All nine findings are closed on
   `claude/gracious-davinci-nnkdv1` — PR #15, a merge of `main` (#16), then the fixes — which is
   the release candidate: 588 tests pass, 0 xfail, and it has run for real against the
   production drive and the production model. **What is left:** merge the release PR; *Deploy to
   Azure* (the live what-if already shows exactly `build → reconcile` and `3600 → 1800 s`, cron
   untouched); *Run the Azure job* → `scheduled` to measure a no-op run on Azure (A-15); then
   arm `*/30` — one reviewed line in `infra/main.bicep` (PLAN Phase 10's STOP).

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
| 2026-09-11 | post-v1 | `validate-config` on Azure: `4 schema(s), 3 output definition(s), 8 propert(ies)`, identical to a local run line for line — the config in the image matches `main`. | The full build |
| 2026-09-11 | post-v1 | **The production host built a full quarter, clean.** `crr-quarterly-ectvlit`, exit 0, **8/8 built, 0 to review**, $4.78. Every published PDF downloaded back out of Drive and checked: page counts match golden exactly, bookmarks and titles correct. B-08 confirmed fixed in production. | Delete the `2026-08` rehearsal tree; load September's real inputs |
| 2026-09-26 | 10 | Phase 10 built and rehearsed on the live drive (PR #15), then audited: nine findings, each reproduced by a probe | Fix what unattended runs would hit |
| 2026-09-28 | 10 | Audit follow-ups on `claude/gracious-davinci-nnkdv1`: main (#16) merged in; tie-break and month-isolation defects fixed; probes kept as tests (563 passed, 3 strict xfail); September cleaned in Drive, the rehearsal moved whole to its own root | Findings 4–6; land the branch in PR #15; merge |
| 2026-09-29 | 10 | Findings 4–6 fixed (close-grace window, Drive retries, run lease) and every document brought up to date; the release candidate live-tested in the production environment — Azure what-if, production no-op and lease race, real-model builds in the rehearsal root on both models — 588 passed, 0 xfail | Merge the release PR; deploy; measure on Azure; arm |

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


## Phase 10 — Continuous intake (built 2026-09-26; at its STOP)

Mirrors PLAN Phase 10; SPEC §18; D-17 – D-24.

- [x] Config: `component_folders` in `properties.yaml`; per-property `components` overrides. `validate-config` covers both. Keyed by role, not by the output definition's alias — the aliases differ per manager and the roles do not (SPEC §18.5 amended). `ConfigBundle.components_for()` drops `not_used`; also rejects a folder named `output`/`SUPERSEDED…`, duplicates, and a property left with no components. 9 tests.
- [x] Repository: list a component folder with head-revision upload times and `md5Checksum`; rename to and from `SUPERSEDED - `; create the month/component/`output` skeleton; read and write `state.json`; publish `vN` names. `crr.intake.store.IntakeStore` with `LocalIntakeStore` and `DriveIntakeStore` (a subclass of the v1 Drive repository, reusing its navigation and preflight). One contract suite runs against both (22 tests). On Drive a file whose `modifiedTime == createdTime` costs no extra call; only a renamed or re-versioned file needs `revisions.list`. The system's own files (status, index, summary) are rewritten in place with `files.update`, so a folder never shows two statuses and no person's file is ever trashed — both pinned by tests.
- [x] File choice (§18.4) and readiness (§18.5), pure, fully unit-tested: newest wins, prefix follows the winner, delete-newest reverts, settle window, optional components, `not_used`. `crr.intake.{files,calendar,decide,state,status}` — no I/O and no clock, so all of §18.4/§18.5/§18.7's decisions and §18.8's headlines are pinned by 37 tests. The per-month index is `output/manifests/state.json` (versions + failed attempts), one small download per month per run instead of every manifest (SPEC §18.7 amended).
- [x] Fingerprint and versions (§18.7); manifest v2 fields; classification reuse from the previous manifest with its compatibility check. Manifest v2 adds `version`, `input_fingerprint`, `omitted_optional` and per input `source_sha256` (pre-OCR — OCR output is not byte-stable, so the post-OCR `sha256` could never match), `schema_sha256`, `upload_name`, `file_id`, `md5`, `uploaded_at`, `reused_classification`. `ReusingClassifier` carries labels over only when bytes, schema hash, classifier name, model and prompt version all match and every page is labelled (7 unit tests). End to end: replacing the Balance Sheet re-classifies exactly one role.
- [x] Open check (§18.6), cost ceiling and three-strike failure cap (§18.7). The ceiling counts only the pages that will actually be sent, so reuse lowers it; it applies to any classifier named `anthropic*` and is zero for golden.
- [x] Status files and root summary (§18.8): every row of the table has a test; bodies carry no page text, tenant names or figures (extend the log-capture test). The page-text check extracts every line of 12+ characters from the input PDFs and asserts none reaches a status or the summary. The summary's "Last checked" line changes every run on purpose: it is the reviewer's only sign the job is still alive.
- [x] `crr reconcile` (§18.9) with `--property`, `--period`, `--force`, `--dry-run`; soft deadline; pre-publish re-list. `crr.intake.reconcile.Reconciler` runs the v1 pipeline unchanged through a staging adapter and publishes the result itself. The duplicate check is "a version appeared since this run read the index, with the same fingerprint" — proven by a test in which a second run executes *inside* the first one's classification. 13 end-to-end scenarios over real June files (`tests/eval/test_reconcile.py`). Smoke-tested from the CLI on a scratch tree: dry run → v1 → idempotent re-run.
- [ ] Verify against Azure docs and one real run: (a) whether a scheduled Container Apps Job execution starts while the previous one is running; (b) the monthly cost of 48 short runs a day. Record both in `QUESTIONS.md`. **Docs half done (A-14, A-15):** overlapping executions run in parallel by default — and since 2026-09-28 the run lease sends the second away, proven live on the production drive; a no-op run measured **48.8 s** against production from a session container (78 % of the free grant at 48/day). **Open:** the same measurement on Azure — needs the merge and a deploy, so it waits for the STOP.
- [x] Hosting (§18.10): Bicep cron and args; `azure-job.yml` gains `reconcile --force`; `build-period.yml` gains `reconcile`. The job now runs `crr reconcile --repo gdrive --classifier anthropic` with a 1800 s replica timeout, **but the cron default stays quarterly** — so no redeploy, including `Run the Azure job`'s automatic restore, can arm the 30-minute schedule before the STOP is cleared; arming is one reviewed line. `--force` went to `Build a period` (a `command` choice: `reconcile`, `reconcile --force`, `build`) rather than `azure-job.yml`: `az containerapp job update --args` cannot carry a multi-token list (A-13), and Actions runs the identical image with no job mutation to restore.
- [x] Rehearsal in Drive: seed a month in the new layout and walk it through every status — partial upload, settle, unopenable file held, built v1, replace one component, v2 with reuse, duplicate upload superseded, delete-newest revert, closed. Record each in `PROGRESS.md`. **Done 2026-09-26 on the live shared drive, Fort Grounds / 2026-09 September**, the uploader played through the Drive API with June files under new names:

  | Step | What a person did | What `output/` said |
  |---|---|---|
  | 1 | nothing | folders for Sep and Oct created; no status |
  | 2 | PM report only | `Waiting for Balance Sheet, Profit and Loss` |
  | 3 | BS and P&L arrive | `Waiting for uploads to settle` (60 min) |
  | 4 | — (settled) | `Built v1 (current)` — golden labels |
  | 5 | — | nothing rebuilt |
  | 6 | corrected BS uploaded | old one renamed `SUPERSEDED - Balance Sheet 9-30.pdf`; `Built v2 (current)` |
  | 7 | a non-PDF named `.pdf` into P&L | `Built v2 - newer files waiting` → **fixed** to `… held` (see below) |
  | 8 | that file deleted | old P&L un-marked; fingerprint equals v2's, so **no rebuild**: `Built v2 (current)` |
  | 9 | corrected BS deleted | original BS un-marked; `Built v3 (current)` |
  | 10 | Distribution Schedule arrives | `Built v4 (current)`, history "Distribution Schedule added" |
  | 11 | upload into July (closed 09-11) | silently ignored — never had a status |
  | 11 | August with a status, window passed | `Closed 2026-08-31 (nothing built)`, once; the next run does not look |
  | 12 | **real model**, `--force` | `Built v5`: 19 calls, **$0.52**, 8 pages (= golden) |
  | 12 | corrected P&L | `Built v6`: **1 call, $0.02** — PM, BS and Distribution labels reused |
  | 13 | full 8-property run | first run 2 m 06 s (creates every property's Sep/Oct folders); **steady state with nothing to build: 37 s** from this container |

  v6 downloaded back out of Drive: 8 pages, 6 bookmarks, title `Fort Grounds - Investor Report - September 2026`. The root `_STATUS - All properties.txt` reads `Fort Grounds - September 2026 - Built v6 (current)`. **Two defects found and fixed** (`aa2c8df`): a replaced component was listed twice in a version's history (`a | b - c` precedence), and a held newer file read as "waiting", which asks nothing of a reviewer. The July/August test months were trashed afterwards; **Fort Grounds / 2026-09 was left in place as a worked example** (v1–v6 and their status); on 2026-09-28 it moved, whole, to the rehearsal root — see *Audit follow-ups*, item 3.
- [x] Docs: `RUNBOOK.md` rewritten around the new layout — a one-page "how to upload" for non-technical uploaders, and "how to read the status" for reviewers; `SETUP-GOOGLE-DRIVE.md`; banners in SPEC §6.1/§6.9/§13/§14 replaced by the amended text. The runbook's operating half is new: *How it works*, *For uploaders — one page* (written to be forwarded as is), *For reviewers* (every status headline, what it means, what to do; the root summary's *Last checked* as the liveness signal), the folder layout, on-demand runs, Azure and how to arm the schedule, and six new failure-mode rows. README, SETUP-GOOGLE-DRIVE, SPEC §11 (CLI) and §12 (settings) updated; the §6.1/§6.9/§13/§14 banners now say those sections describe `crr build`.

**Acceptance, 2026-09-26:**
- *Every rehearsal scenario produces its §18.8 status and no build it should not* — **met**, on
  the live drive (table above), after the two defects it found were fixed.
- *An unrelated PDF of any length costs at most `CRR_MAX_BUILD_USD`* — **met**: the ceiling is
  checked before any model call and counts only pages that would be sent (test
  `test_the_cost_ceiling_holds_and_reuse_lowers_the_estimate`).
- *A run with nothing to build finishes in under a minute on Azure* — **37 s from this
  container against the live drive; not yet measured on Azure** (needs a deploy — the STOP).
  Re-measured 2026-09-29 with the run lease and preflight: **48.8 s** against production, flat
  with history since fix 4.
- *Keyed eval unchanged at 100 %* — **met by construction**: `src/crr/classify`, `segment`,
  `resolve`, `compose`, `config/schemas`, `config/outputs` and `eval/golden` are byte-identical
  to `main`, and the prompt version is unchanged; the golden gate passes in the suite (542
  tests), and the real-model rebuild of Fort Grounds matched golden (8 pages, 6 bookmarks).

### Audit follow-ups (2026-09-26)

An audit of PR #15 reproduced nine findings with probes run against the branch head `286dc89`.
Every probe is now a test. This work is on `claude/gracious-davinci-nnkdv1`, which is PR #15's
head plus a merge of `main` (#16 had made two docs lines conflict) plus the commits below.

- [x] **1. A tie on upload time flipped the winner on every run** (`b6f5505`). `choose()` broke
  ties on the file name and then renamed the loser `SUPERSEDED - …`, which changed the
  tie-break: two PDFs uploaded at the same instant produced a new version, and a paid
  re-classification, on every run. Ties now break on the name without the prefix, then the id.
  SPEC §18.4 amended. The unit test now applies the renames between runs; an end-to-end test
  runs four times over two equal-time Balance Sheets and gets one version.
- [x] **2. One bad property-month stopped the whole run, on every run** (`9891fa9`). An index
  the code could not read (a state.json with one unexpected key — what an older image meets
  after a rollback), a folder named `2026-13 …`, or one Drive error ended the run; every month
  after it went unchecked and the root summary was never written. Months are now checked in
  isolation. A failing month gets `Could not be checked - will retry` (only over an existing
  status), and the summary is always written, listing it. `reconcile` exits 1 after the rest is
  done. Folders that only look like months are skipped. `RunAborted` keeps a missing API key a
  run-level stop. SPEC §11/§18.3/§18.8/§18.9, RUNBOOK and README amended.
- [x] **Probes kept as tests** (`6bde5d7`). NEEDS REVIEW publishing, `--period`, cross-month
  drift, and the password, owner-password and zero-page cases now run; coverage had shown them
  never executed. Two behaviours are pinned: `--force` reuses every unchanged label, and the
  cost ceiling is per attempt.
- [x] **3. Live-Drive hygiene — done 2026-09-28**, approved by the operator. September was a
  live month still holding the rehearsal: five input PDFs byte-identical to the June bundle
  (the "revised" P&L is the June P&L plus `\n%revised\n`), v1–v6, manifests, state.json and
  status. A real September upload would have been combined with June statements and
  published as `v7 (current)`. Drive was re-verified against the 2026-09-26 inventory first
  (26/26 items identical). Then, in order:
  1. **The record went to git before Drive was touched** (`ca76a15`,
     `eval/reports/rehearsal-2026-09-fort-grounds/`): inventory with ids and md5s, how to
     rebuild each input from the bundle, status, state.json and v1–v6 manifests (model-written
     `evidence` replaced by a marker), from a download whose every file matched Drive's md5.
  2. Created `Cornerstone Reports - REHEARSAL (test data, not for investors)`
     (`1eGZGlv5IGVd7OGM0-_2jcDfa56FkwAlz`) beside the production root in the shared drive,
     with `Missoula Property Management/Fort Grounds/` inside it.
  3. Trashed the eight empty `2026-09 September/inputs/` folders (v1 leftovers that
     `reconcile` ignores silently; restorable from Drive's trash for 30 days).
  4. Moved the rehearsal month there whole: 25/25 items with their ids and md5s. Pointed at
     that root, `reconcile --dry-run` reads it as `Built v6 (current)`: it is a working
     rehearsal environment (RUNBOOK → *Rehearsing without touching a real month*).
  5. On the production root, a write-blocked dry run showed all 16 open property-months empty.
     A real `reconcile` pass in which a build was impossible then recreated Fort Grounds'
     September skeleton (the month, four numbered folders, `output/`) and rewrote the root
     summary, which had still read `Built v6`.

  Verified afterwards: every property's September and October hold exactly the four numbered
  folders and `output/`, with no files; the root holds the three manager folders and the
  summary. Every Drive write is logged, with ids, in
  `eval/reports/rehearsal-2026-09-fort-grounds/drive-operations-2026-09-28.json`.
- [x] **4, 5, 6 — fixed 2026-09-28** as recommended below: a close-grace window
  (`98f8a84`), retries on every Drive request with safe folder creation (`2bcd21e`), and a run
  lease (`dd06f75`). The strict xfails that held them now pass as ordinary tests
  (`tests/eval/test_reconcile_operations.py`, `tests/unit/test_drive_client_retries.py`).
- [x] **Documents** (`30e4e7f`): the setup guides and infra README described the old quarterly
  `build`; D-20, README, RUNBOOK `--force` cost, PLAN's per-attempt ceiling, SPEC §18.8.
- [x] **4. Closed months are re-read on every run.** Each costs 3 Drive calls: 126 calls with no
  history, 414 with a year of it (strict xfail
  `test_a_no_op_run_does_not_grow_with_closed_history`). *Recommended:* only consider closing a
  month within a grace period after its close date (`CRR_CLOSE_GRACE_DAYS`, say 14). Beyond
  that it was closed by an earlier run, so skip it without a Drive call. Check the status by
  name from one listing, not by downloading its body.
- [x] **5. Drive requests are not retried** (strict xfail `test_drive_requests_are_retried`).
  *Recommended:* `execute(num_retries=5)` on every request in `GoogleDriveApi`, and the same on
  `MediaIoBaseDownload.next_chunk`. googleapiclient then backs off on 5xx, 429 and rate-limit
  403s. It is all in one file, the seam the fake replaces. Since fix 2, whatever still fails
  after retries costs one month one run, not the run.
- [x] **6. A run landing between a build's publish and its state.json write publishes a
  duplicate**, and the index keeps only one of the two (strict xfail
  `test_a_run_landing_between_publish_and_commit_publishes_no_duplicate`). *Recommended:* a run
  lease — one system file in the root, written, read back to confirm ownership, expiring after
  the 1800 s replica timeout. A second execution finding a live lease exits 0 at once. That
  closes this window and concurrent folder creation at month rollover, and keeps the duplicate
  check as a backstop. Until then, do not run *Build a period* → `reconcile` while an Azure
  execution is running.
- [x] Still open from the audit, documents only (closed by `30e4e7f`): D-20 names the wrong workflow for `--force`;
  the README says "every 30 minutes" before the schedule is armed; the RUNBOOK's
  "$0.60 per property-month" for `--force` is ≈$0 with reuse; PLAN's "at most
  CRR_MAX_BUILD_USD" is per attempt; `azure-job.yml`'s `build (…)` option now starts a
  reconcile run.

### Live test (2026-09-29): the release candidate in the production environment

Real Azure, real Drive, real model. Nothing was uploaded into the production root: builds ran in
the rehearsal root (the same shared drive, service account and API key), and the production root
had no-op runs only.

| # | Where | What | Result |
|---|---|---|---|
| 1 | Azure, live resource group | *Deploy to Azure*, what-if only, from the release branch ([run 36499470034](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/36499470034)) | `crr-quarterly`: `args[0] build → reconcile`, `replicaTimeout 3600 → 1800`, **schedule untouched**; the rest is what-if noise (Key Vault URLs as expressions, environment defaults). Nothing deployed. |
| 2 | Production root | `crr reconcile --dry-run` | 16 open property-months, nothing to build; 39 s |
| 3 | Production root | real `crr reconcile` | preflight, lease, 16 months checked, summary rewritten, exit 0; **48.8 s** |
| 4 | Production root | two real runs started together | one worked; the other lost the lease race and printed `nothing done: another run (vm) holds the lease until …`; both exit 0 |
| 5 | Rehearsal root | first real run in the new root | 99 folders created; Fort Grounds' archived month read as `Built v6 (current)` |
| 6 | Rehearsal root | Timber Place's June files uploaded; the default 60-minute settle | `Waiting for uploads to settle` |
| 7 | Rehearsal root | real model (`claude-opus-5`), settle 0 | `Built v1 (current)`: OCR, 25 calls, one orientation disagreement arbitrated. Downloaded back: 25 pages, 13 bookmarks, title right, **plan identical to golden** including `rotate:90` on page 5 (`/Rotate 90`, 792×612). $0.80, 278 s |
| 8 | Rehearsal root | a corrected Balance Sheet uploaded | `Built v2 (current)`: **1 call**, PM and P&L labels reused — the scanned PM source across OCR — and the old file renamed `SUPERSEDED - …`; $0.02 |
| 9 | Rehearsal root | `--force` on production's model, `claude-opus-5-5` | `Built v3 (current)`: 25 calls, nothing reused (the model changed); **plan identical to golden**, rotation included; $0.62, 226 s |
| 10 | Rehearsal root | Timber Place's state.json edited by hand | that month `Could not be checked - will retry`, listed in the root summary, Fort Grounds unaffected, exit 1; restored as the RUNBOOK says → `Built v3 (current)`, exit 0 |
| 11 | Production | `pytest -m "api or gdrive"`, `claude-opus-5-5` | 8 passed |

Model spend for all of it: **$1.44**. The rehearsal root now holds Timber Place / 2026-09 v1–v3
beside Fort Grounds' v1–v6; the production root gained only its lease file and a refreshed
summary. Why step 9: this container sets `CRR_MODEL=claude-opus-5`, while the Azure job sets no
model and so runs the default, `claude-opus-5-5`.

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
