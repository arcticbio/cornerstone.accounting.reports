# Open questions and checkpoint protocol

## How to use this file

**Claude Code:** when you hit something the spec does not settle and a sensible default exists,
take the default, record it under "Assumed" with the reason, and keep going. When no sensible
default exists, or the choice is irreversible or costs money, write it under "Blocked", commit,
and end the turn with a message beginning `CHECKPOINT:`. Do not wait idle: move to the next
unblocked task in `PLAN.md`.

**User:** answer under the question, commit (or reply in the session), and the next session picks
it up from here.

---

## Awaiting user

*(none yet — the build has not started)*

---

## Pre-answered defaults (already decided; listed so nobody re-asks)

| Question | Answer |
|---|---|
| Which model? | `claude-opus-5`, temperature 0 (D-09) |
| Do we reproduce the Missoula Balance Sheet pages? | No — no source (D-03) |
| Record order for WayPointe? | Source order: WayPointe AH LP, then 128 S. 5th (D-07) |
| Should McCathren outputs be searchable? | Yes — OCR output is the composed source (D-10) |
| Where do new periods live? | Google Drive, not git (D-08, D-14) |
| Host? | GitHub Actions first; Azure when credentials arrive (D-13) |
| Bookmarks in the output PDF? | Yes, one per section (SPEC §6.6) |
| Output filename? | `"<Property> - Investor Report - <Month YYYY>.pdf"` |
| Period folder name? | `"YYYY-MM <Month>"`, e.g. `2026-09 September` |
| Rendering DPI? | 150, long edge ≤ 1568 px |
| Confidence threshold? | 0.85 |
| What if `ocrmypdf` is missing in the environment? | Fail the McCathren builds with a clear message; never silently skip OCR |

---

## Assumed (Claude Code appends here)

*(format: `A-nn · <assumption> · <why> · <where it can be changed>`)*

**A-01 · `ocrmypdf` is located via `CRR_OCRMYPDF_BIN`, defaulting to `ocrmypdf` on PATH.**
*Why:* the build container ships a Debian `ocrmypdf` built for python3.12 while `/usr/bin/python3`
is a locally built 3.11, so the stock entry point cannot import PIL. Rather than special-case that
in pipeline code, the entry point is one setting with the spec'd default; the session uses a
git-ignored shim in `.venv/bin/`. CI and the Docker image use the stock apt entry point unchanged.
*Where:* `src/crr/preprocess/ocr.py`, `SPEC.md` §12 (amended in the same commit).

**A-02 · `temperature` is not sent to the classifier; `output_config.effort=low` replaces it.**
*Why:* SPEC §7.2 specified `temperature=0`, but the parameter is rejected with a 400 on
`claude-opus-5`. The safest equivalent is the one already in the design — a forced tool with a
closed `enum` and `strict: true` — plus low effort, since page classification is perceptual, not
a reasoning task. *Where:* `src/crr/settings.py` (`CRR_CLASSIFIER_EFFORT`), `SPEC.md` §7.2/§12
(amended in the same commit).

**A-03 · Exemplar images sit at the head of the user turn, not in the system prompt.**
*Why:* SPEC §7.2 put them in the system block so they would cache, but the Messages API's
`system` field accepts text blocks only. They now lead the user turn with their own 1-hour cache
breakpoint, which preserves the caching behaviour the spec was actually after. *Where:*
`src/crr/classify/anthropic_classifier.py`, `SPEC.md` §7.2 (amended in the same commit).

**A-04 · No server-side refusal fallback model is configured.**
*Why:* a `stop_reason: "refusal"` on a page of a rental property's financial report would be
surprising, and adding a second model behind a beta flag widens the failure surface of an
unattended quarterly job. A refusal is handled as `unknown` → review, which is the same
conservative path as an unparseable response. Revisit if a real run ever refuses.
*Where:* `src/crr/classify/anthropic_classifier.py`.

**A-05 · Built-in price table set to current list prices for `claude-opus-5` ($5/$25 per MTok,
cache read 0.1×, cache write 2× at the 1-hour TTL).**
*Why:* SPEC §12 leaves the built-in table to the implementation. The estimate only ever appears
in the manifest's `cost.usd_estimate`; `CRR_PRICE_TABLE_JSON` overrides it when list prices move.
*Where:* `src/crr/settings.py`.

**A-06 · The local repository publishes under `<work_dir>/published`, not beside the inputs.**
*Why:* SPEC §6.1 has the local repository publish into `<period>/output/`, but the local root is
the June bundle, which `CLAUDE.md` and D-08 make read-only. A golden build would otherwise write
eight `output/` directories into the fixture. Publishing mirrors the same layout under
`CRR_PUBLISH_ROOT` instead; set it to `bundle_root` to get the in-place behaviour. Drive (Phase 6)
publishes in place, as production should. *Where:* `src/crr/settings.py`,
`src/crr/repository/local_fs.py`, `SPEC.md` §6.1/§12 (amended in the same commit).

**A-07 · `crr build --period` is optional, defaulting to the month just ended.**
*Why:* the Azure job and the Actions cron both fire on a schedule, and a required `--period`
would mean either editing the template every quarter or baking a fixed period into a recurring
job — which would silently rebuild the same period forever. A run on the 20th of January closes
December, so "the previous calendar month" is the period a scheduled run is for. Passing
`--period` explicitly is unchanged. *Where:* `src/crr/cli.py`,
`src/crr/config/properties.py`, `SPEC.md` §11 (amended in the same commit).

**A-08 · v1 classifies zero-shot: the exemplar mechanism is built but not wired in.**
*What is true:* SPEC §7.2 item 4 and §8 describe up to two labelled exemplar pages per section,
drawn from `eval/golden` under `exemplar_policy`. `select_exemplars()` and
`build_exemplar_blocks()` exist and are unit-tested, but the only place that constructs an
`AnthropicClassifier` — `cli.py` — passes no exemplars. So **both `crr build --classifier
anthropic` and `crr eval --classifier anthropic` run zero-shot**, and `exemplar_policy` has no
effect on either.
*Why it is being recorded rather than "fixed":* the zero-shot numbers are already at ceiling
(see the eval report), so adding ~20 images to every request would multiply the per-run cost for
no measurable accuracy. It also explains the cost gap — the ~$10 modelled estimate assumed
exemplars; the measured run without them is $4.72.
*The decision this leaves open:* either wire exemplars in (and re-measure cost and accuracy on a
period where accuracy is not already perfect), or amend SPEC §7.2 to say v1 ships zero-shot by
choice. Worth revisiting the first time a new manager's schema scores below threshold — that is
exactly the case exemplars are for.
*Where:* `src/crr/cli.py` (`_make_classifier`), `src/crr/classify/prompts.py`, SPEC §7.2/§8.

**A-09 · Orientation is decided by a cross-check, not by the classifier alone.**
*What the eval found:* the real-model eval scored **orientation 0.00 % (0/1)**. On Timber Place
page 3 — the only rotated page in the corpus — the classifier answers `rotated_90_cw` where the
truth is `rotated_90_ccw`, the opposite direction, at 0.96 confidence. The composer applied the
complementary rotation and **the aged-receivable page shipped to investors upside down**, with
page counts, dimensions, both eval gates and every review code passing, because either rotation
yields the same 792x612 landscape page. Only the eval's orientation metric saw it.
*What was tried and did not work:* rewriting the prompt rule twice — once to lead with the edge
the top of the content faces, once to key purely on the reading direction, with the mapping given
as a lookup table. The first went from 1-in-4 right to 0-in-4; the second was 0-in-6, and the
model's *evidence* string contradicted its own label ("reading bottom-to-top" → `rotated_90_cw`).
Both prompt versions were reverted rather than shipped: a `prompt_version` bump costs a re-eval
and neither bought anything.
*What was taken instead:* two independent signals must agree before the composer turns a page
(SPEC §7.6). Tesseract OSD at 400 DPI agreed with all **172/172** golden pages. It is not
authoritative either — over the 150 DPI classifier images, ink-cropped and upscaled, the same
detector called eight upright pages `rotated_180`, three of them at higher confidence than the
page it got right, so **OSD confidence is not a safety margin**. On disagreement an arbiter shows
the page in all four rotations, shuffled, and asks which reads normally: a discrimination, not a
mental rotation, and **12/12** including the page the naming task never gets right. Unsettled →
`orientation_uncertain` and a human (D-12).
*Cost:* one 400 DPI render plus a tesseract run per page, and one extra API call per
disagreement — one page in 172. Timber Place rebuilt clean end to end at $0.74 and the shipped
page now reads right-side-up.
*The decision this leaves open:* whether `orientation` should stay in the classifier's tool
schema at all. It is now only ever a hint, and dropping it would save output tokens — but it is
also the signal the cross-check is measured against, so it stays until a second rotated page
exists to test with.
*Where:* `src/crr/preprocess/orientation.py`, `src/crr/classify/orientation_check.py`,
`src/crr/classify/orientation_arbiter.py`, SPEC §6.2/§6.5/§6.8/§7.6/§12.

**A-10 · The `record_qualifier` metric scores the resolved record, not the printed string.**
*What the eval found:* Missoula record accuracy **59.38 % (38/64)** on a run where page
accuracy, continuation and boundary F1 were all 1.0000, every Missoula property resolved to its
exact golden page count, and no build raised `unresolved_record`. Those cannot all be true of a
classifier that is wrong about records 40 % of the time.
*Root cause, measured not inferred:* a real-model run over Fort Grounds' PM source (16 pages)
shows the model transcribing `Fort Grounds Apartment Homes` on each of the 8 section-head pages
— Rent Manager prints a `Property:` header there — and `null` on the continuation pages. The
golden file carries `null` on all 16, because `map_qualifier` maps null *and* an exactly
matching `pm_name` to the same record on a single-record property. Comparing the raw strings
therefore marked all 8 head pages wrong. Checked page by page: **0 of 16 pages resolve
differently** with the transcription than with null. The metric was measuring transcription,
not correctness.
*What changed:* both sides of the comparison now go through `map_qualifier`, so the metric
scores the record a page lands in. Fort Grounds goes 8/16 → 16/16 with no change to any label.
*And a second cause behind the first:* that took Missoula to 96.88 % (62/64), not 100 %. The
remaining two were WayPointe pages 4 and 7 — `unit_availability` **continuations** where the
model correctly returned `null`, exactly as the prompt instructs, and where a bare null on a
multi-record property resolves nowhere. The metric was scoring each page in isolation, without
the §6.4 continuation inheritance the segmenter applies before it maps anything. Scoring the
*effective* qualifier closes it: **100.00 % (64/64)**. Boundary F1 was 1.0000 throughout, which
was the standing clue that no section was ever filed under the wrong record.
The metric does not become vacuous — a qualifier matching no record still scores wrong, and so
does a non-continuation page that inherits nothing, both pinned by tests over the real labels.
*What did not change:* nothing in the pipeline. No label, no plan, no output page. This was a
reporting defect, and worth contrasting with A-09, which looked similar in the report and was a
real page shipping upside down. A number that disagrees with the rest of the report is worth
running down either way.
*Recommendation for next time:* `crr eval` does not persist per-page predictions, so re-scoring
under a corrected metric costs a full keyed run ($4.66). Dumping the predictions beside the
report would make metric changes free to re-measure.
*Where:* `src/crr/evaluate/metrics.py`, `src/crr/evaluate/harness.py`, SPEC §8,
`tests/unit/test_record_metric.py`.

**A-11 · A rehearsal period `2026-08` was seeded into Drive so the job can be started with no
arguments.**
*Why:* `infra/main.bicep` bakes `build --repo gdrive --classifier anthropic` with **no
`--period`**, because a quarterly run on the 20th is closing the month just ended (A-07). That
makes the no-argument start the only faithful rehearsal of what the cron actually does — and
today the month just ended is `2026-08`, which had no inputs. A start against an empty period
proves nothing except that the period is empty.
*What was seeded:* 31 files across all eight properties under `inputs/2026-08`, copied from
`data/bundle/2026-06`. **The content is June's, under an August label.** It is a rehearsal
dataset. Any package it produces is labelled August and contains June figures, so it must not be
mistaken for a deliverable and the `2026-08` tree should be removed once the rehearsal is done.
*The alternative, and why not:* start the job with `--args build --period 2026-06 …` against the
real June inputs. That exercises the image, the vault and Drive equally well but not the
defaulting, which is the one piece of the schedule's behaviour that has never run. Both are
available from `Actions → Run the Azure job`.
*Where:* Drive `inputs/2026-08` (delete it there); nothing in the repository depends on it.

**A-12 · The setup documents gave the old My Drive folder id, not the shared-drive one.**
*Found 2026-09-11* while tidying Drive, which is the only reason it was found at all.
`SETUP-CREDENTIALS.md`, `SETUP-AZURE-PORTAL.md` (in two places) and `infra/README.md` all still
printed `1_tUMelVG8…` as the value to paste into `CRR_GDRIVE_ROOT_FOLDER_ID`. The live
configuration was already correct — GitHub and Azure both carry the shared-drive id — so nothing
was broken; but anyone setting up a second environment by following those documents would have
pointed the runner at a My Drive root and **reproduced B-09 exactly**, right down to the failure
mode where folders create fine and every upload 403s.
*What changed:* all four now carry `1SQUgfGiw1…` and a sentence saying the root must be in a
shared drive, with the reason and a link to `SETUP-GOOGLE-DRIVE.md`.
*The lesson:* a resolved blocker leaves copies of the broken value behind in the documents that
told you to set it. Grepping for the old value is the check, and it costs one command.
*Where:* `docs/SETUP-CREDENTIALS.md`, `docs/SETUP-AZURE-PORTAL.md`, `infra/README.md`. The
remaining occurrences in `PROGRESS.md` are historical record and are correct as history.

**A-13 · A manual Azure run is restored by re-deploying the template, not by setting `--args`
back.**
*What the first live run found:* `az containerapp job update --args` sets a single-token command
fine and **cannot set the real argument list at all**. The CLI's parser reads every
`--`-prefixed token after `--args` as one of its own flags:

```
$ az containerapp job update ... --args build --repo gdrive --classifier anthropic
ERROR: unrecognized arguments: --repo gdrive --classifier anthropic
```

No quoting fixes it — `--args="a b c"` yields one argv element, not three — and there is no `--`
escape. This is the same family as the `job start` limitation already recorded in
`SETUP-AZURE.md` step 7 (azure-cli#27521), and it is worse, because it is *asymmetric*: the
smoke test can set `version` and then cannot put the schedule's arguments back. The first run of
`Run the Azure job` did exactly that and left `crr-quarterly` holding `version`, which the
20 October cron would have run to no effect. Caught by the workflow's own verification step,
repaired by a deploy the same hour (what-if diff: `- 0: "version"` → `+ 0: "build" …`).
*What changed:* the workflow no longer accepts free-text arguments — a `choice` of `version`,
`validate-config`, or the job's own scheduled arguments unchanged, so a `--`-prefixed token can
never reach `--args`. The restore is a *call* to `deploy.yml` as a reusable workflow, so it
cannot drift from the deploy, and a third job then re-reads the job and compares it against the
template. Anything else — another period, one property — goes through `Build a period`, which
runs the identical image and mutates nothing.
*Also fixed:* reading an execution's logs took three attempts, and the fix that mattered was
making the failure *say something*. `az containerapp job logs show` selects an execution with
**`--execution`** (guessed as `--job-execution-name` — cost run 1's logs) and **caps `--tail` at
300** (`ERROR: --tail must be between 0 and 300` — cost run 2's logs). Both were found by the
`--help` dump the step now performs when the call fails, which is the only reason the second one
took one run rather than another guess. `--format text` as well: the default is JSON-wrapped.
*The lesson:* "set X, do work, set X back" is only safe when both directions are known to work.
The first run proved the setting direction and assumed the restoring one.
*Where:* `.github/workflows/azure-job.yml`, `.github/workflows/deploy.yml` (`workflow_call`),
`docs/SETUP-AZURE.md` step 7, `docs/RUNBOOK.md`.

---

## Blocked (Claude Code appends here)

*(format: `B-nn · <what is needed> · <what is blocked> · <what continues meanwhile>`)*

**B-01 · ~~The classifier key does not reach the Claude Code session container.~~ RESOLVED.**
*Root cause:* **Claude Code on the web reserves the name `ANTHROPIC_API_KEY`** — sessions
authenticate their own model calls through the user's Anthropic account, so the platform strips
that variable before the container starts. The cloud-environment editor says so under the
variables box. It was misread twice as an injection-timing problem; the evidence that separates
them is that `CRR_MODEL`, `CRR_GDRIVE_ROOT_FOLDER_ID` and `GOOGLE_SERVICE_ACCOUNT_B64` all arrive
from the same environment in the same session while `ANTHROPIC_API_KEY` is empty. One name is
filtered, not the whole environment.
*Fix:* `settings.py` reads `AliasChoices("CRR_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")`. The user
renamed the variable; a session now resolves the key locally. GitHub Actions and Azure keep the
conventional name — `build-period.yml` still passes `secrets.ANTHROPIC_API_KEY`, unchanged.
*Both halves are closed:* the Actions half by run
[34524350634](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34524350634)
(a 400 on the tool schema, not a 401), and the session half by this fix. `pytest -m api` and a
local `crr eval --classifier anthropic` both run in-session now.

*Note for whoever reads this next:* the fix lived only on the abandoned branch
`claude/ecstatic-goodall-ji7yur` (PR #2) for a while, so `main` carried the diagnosis without the
alias — which is why an intervening session concluded the local key path was impossible. It is not.

**B-02 · ~~GitHub Actions has not run CI on PR #1.~~ RESOLVED 2026-09-10.**
Green on the final tree `943e664`: runs
[34464245438](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34464245438)
(push) and
[34464250151](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34464250151)
(pull_request), all three jobs — lint/types/tests/validate-config/eval gate, the Bicep compile,
and the image job with its in-container golden build and GHCR push.

**B-03 · ~~No container runtime in the build environment.~~ RESOLVED 2026-09-10 in CI.**
Still true locally — `/var/run/docker.sock` does not exist here — but CI's `image` job builds
the image, runs `crr version`, proves `/app/data` is absent, checks all three OCR binaries
inside the container, runs the golden build there, and pushes to GHCR. All green.

**B-04 · ~~Azure deployment.~~ RESOLVED 2026-09-11 — deployed, audited and armed.**
*What is live,* read out of the *Deploy to Azure* run logs rather than assumed: runs 3–7
succeeded, the latest at 03:48 UTC from `main`@`020fc7d`. Subscription `e7eadf09…`, resource
group `rg-cust-cornerstone`, job `crr-quarterly`, environment `crr-env`, workspace `crr-logs`,
vault `crr-kv-accounting`. The job's system-assigned identity `e3de70d7…` already reads the
vault — the grant step reported "nothing to do", so step 6's warning path is not outstanding.
GHCR pull credentials are supplied, so the private package is reachable. `scheduleEnabled=true`,
cron `0 6 20 1,4,7,10 *`.
*The line that mattered in the what-if diff:* `~ value: "1_tUMelVG8…" => "1SQUgfGiw1…"` — Azure
took the **shared-drive** root folder id, which is what carries B-09's fix into the job.
*What is still only the user's to do:* see **B-11** — this session cannot start the job.
*Superseded status 2026-09-10:* the user wants Azure and has a subscription, and is working through setup
in the portal. Two walkthroughs: `docs/SETUP-AZURE.md` (CLI, with `infra/bootstrap.sh` doing the
credential-bearing parts in one guided run) and `docs/SETUP-AZURE-PORTAL.md` (click by click,
with the three unavoidable commands run in Cloud Shell). `deploy.yml` reads its settings from
repository variables so a deploy is one click, and CI publishes the compiled ARM template as an
artifact so a portal-only deployment uses a template that provably compiles.
*Still needs the user, and cannot be done from a session with no Azure credentials:* the
`az login` bootstrap, pasting `AZURE_CREDENTIALS` / `AZURE_RESOURCE_GROUP` /
`AZURE_KEY_VAULT_NAME` into GitHub, and choosing whether the GHCR package goes public or gets a
pull token. *Then:* Phase 8 task 4 — deploy, smoke-run `version` and `validate-config`, capture
the logs into `PROGRESS.md`.

**B-05 · ~~The `v1.0.0` tag cannot be pushed from this session.~~ RESOLVED 2026-09-10.**
The user pushed it. The package version was `0.1.0` at the time and is now `1.0.0`, so
`crr version` and every manifest's `runner_version` match the tag.

**B-06 · ~~CI runs kept being cancelled by the workflow's own concurrency group.~~ RESOLVED.**
`cancel-in-progress` on `ci-${{ github.ref }}` means each push cancels the previous run, and
committing per task meant runs were routinely superseded before their slow steps finished.
Twice I read a superseded run's stale step data as a stall; it was not one. Once pushing
stopped, the run went green. Left as-is — cancelling superseded runs is the right default, and
`cancel-in-progress: false` is the one-line change if it ever becomes a nuisance.


**B-09 · ~~A shared drive for the Drive root.~~ RESOLVED 2026-09-11 — a package has reached
Drive.**
*Proof, end to end on the live account:* the operator created the shared drive
**Cornerstone Investor Reports**, added the runner as **Content manager** (`fileOrganizer`),
created a fresh `Cornerstone Reports` root inside it and re-pointed
`CRR_GDRIVE_ROOT_FOLDER_ID`. Then: `crr preflight --repo gdrive` passes; the 2026-06 and 2026-09
skeletons build out to **43 folders, all owned by the drive rather than by the service account**;
Fort Grounds' four June inputs upload; and `crr build --period 2026-06 --property fort-grounds
--repo gdrive` runs clean — `built`, 8 pages, no review reasons — publishing
`Fort Grounds - Investor Report - June 2026.pdf` and its manifest into `output/`. Downloaded back
out of Drive it is 8 pages, 6 bookmarks, correct `/Title`, **owned by the drive**. The original
diagnosis below is kept because it explains why this took a day to see.
*Cleaned up 2026-09-11:* that test package, its manifest and the four June inputs are trashed now
that they have served their purpose, along with the 29 empty folders in the old My Drive root —
so do not go looking for them. Trashed, not permanently deleted: recoverable for 30 days, and a
Content manager cannot permanently delete in a shared drive anyway. The skeletons remain.
*Two traps found while fixing it, both now in `SETUP-GOOGLE-DRIVE.md`:* the old root could not be
*moved* (the service account owned every folder under it, and Drive will not move what you do not
own — it did not need moving, the tree was 29 empty folders); and the runner's preflight cleanup
used permanent delete, which in a shared drive only a **Manager** may do, so on a correctly
configured drive it left one probe file per run. It trashes now.

*Original diagnosis:*
*Symptom:* uploading any file as the service account fails with
`403 storageQuotaExceeded: Service Accounts do not have storage quota. Leverage shared drives,
or use OAuth delegation instead.`
*Root cause:* the Drive root `Cornerstone Reports` (`1_tUMel…`) is a **My Drive** folder owned by
a person. A service account has no storage quota of its own, and a file uploaded into My Drive
must be owned by the uploader. Folders are exempt — they consume no quota — which is why
`ensure_period_skeleton` succeeds and makes the account look healthy right up until the first
byte is written. `canAddChildren` is `true`; it is not a permission problem, and no amount of
sharing fixes it.
*Blast radius:* not just input staging. `GoogleDriveRepository.publish` uploads the built PDFs
the same way, so **no package can ever reach Drive in this configuration** — a gdrive build
would classify, compose, and fail at the last step.
*Fix, in order of preference:*
1. **Shared drive.** Move `Cornerstone Reports` into one and add
   `crr-runner@cornerstone-reports-508208.iam.gserviceaccount.com` as **Content manager**. Files
   there are owned by the drive, not the uploader, so the quota question never arises. The client
   already sends `supportsAllDrives=true`, so this needs no code change. Needs Google Workspace.
2. **Domain-wide delegation.** The account impersonates a real user, who owns the files. Needs a
   Workspace admin and a `subject=` argument when building credentials — a code change.
*Meanwhile:* `--repo local` is unaffected, and reads from Drive are unaffected.
*How to fix it:* **[`SETUP-GOOGLE-DRIVE.md`](SETUP-GOOGLE-DRIVE.md)** — a 20-minute click-through
in the Drive UI, written 2026-09-11. Verify with `crr preflight --repo gdrive`.
*A second-order trap, found 2026-09-11 while following that document:* **you cannot move the
existing root into a shared drive.** The same quota rule that blocks uploads is why the runner
was able to create folders — they cost no quota — so `ensure_period_skeleton` made the whole
`<manager>/<property>/<period>/inputs/` tree and the **service account owns every folder in it**.
Drive will not let a person move items they do not own, and ownership cannot be transferred from
a service account to a user in another domain. Measured on the live Drive: **29 folders, 0 files,
0 bytes, 29 of 29 owned by `crr-runner@…`**, confirmed independently by
`crr inspect --repo gdrive --period 2026-09` reporting 0/8 properties ready. So there is nothing
in the tree to preserve: create a fresh root *inside* the shared drive and re-point
`CRR_GDRIVE_ROOT_FOLDER_ID`, which is what the document now says.
*What changed in code 2026-09-11:* nothing that fixes it — only that it now fails in a second
instead of at the end. `publish` is the last stage, so a gdrive run used to classify and compose
all eight properties (~$4.72) before the first byte was refused, every time.
`SourceRepository.preflight_publish()` writes one byte to the root and removes it, `crr build`
runs it before constructing a classifier, and the error names the remedy and this document. The
probe was confirmed against the live account: it reproduces `storageQuotaExceeded` exactly
(SPEC §6.1).
*Documentation that was wrong:* `RUNBOOK.md` → *Access* said sharing the root folder as Editor
was sufficient for the runner to "write `output/` and `review/`". It is sufficient to create
those folders and to read; it is not sufficient to put a file in them.

---

**B-10 · ~~PR #6 and PR #7 overlap and neither is redundant.~~ RESOLVED 2026-09-11 — and the
prediction in it was wrong.** (Recorded here as B-10: this was filed as B-09 before the Drive
blocker above merged to `main` and took that number.)

*What was recorded:* that #6 and #7 carried the same B-08 fix, key alias and portal guide
"written independently", so merging either would conflict the other in `SPEC.md`,
`PROGRESS.md`, `QUESTIONS.md`, `segmenter.py` and `settings.py`. The recommendation — merge #7
first, because its Azure content was the guide in live use — was right, and the operator merged
it at 01:33.

*What was wrong:* the two were **not** written independently. #7 branched off
`claude/gifted-lamport-wwgenm` at `a3deab3`, so the B-08 fix, the key alias and the A-08 note
were literally the same commits, shared history rather than parallel reimplementations. Merging
`main` back produced **no conflicts at all** — eight files, all fast-forward. The diff that
prompted the warning (`segmenter.py | 4 +-`, `SPEC.md | 63 +---`) was mostly *this* branch's
later commits that #7 lacked, read as if it were divergence in the shared files.

*The lesson worth keeping:* `git diff A B` answers "how do these differ", not "were these
written independently" — `git merge-base` answers that, and it was one command away. A cheap
check would have replaced a paragraph of confident speculation with a fact.

*What was right and worth keeping:* #7 was not redundant and should not have been closed on
that assumption; its Azure content was written against the live subscription and carries the
`AADSTS7000215` trap, the `Run now`-is-a-production-build correction, and the Drive blocker now
recorded as B-09 above.

**B-11 · This session cannot start the Azure job or read its executions.**
*What is needed:* nothing from the user, as it turns out — but it is worth recording why, because
it was the one gap the audit could not close directly. The session container has no `az` CLI and
no Azure credential (`env | grep AZURE` is empty; `AZURE_CREDENTIALS` is a *repository* secret,
readable only by a workflow run). So `az containerapp job start`, `job execution list` and
`job logs show` are all out of reach from here, and so is any direct read of the deployment's
current state — the Azure facts in B-04 come from the *Deploy to Azure* run logs, which are
readable through the GitHub API.
*What was blocked:* pressing the button on a smoke test and reading back its logs.
*What was done instead:* `.github/workflows/azure-job.yml` — `Actions → Run the Azure job`. It
runs inside Actions, where `AZURE_CREDENTIALS` exists, and does the `SETUP-AZURE.md` step 7
sequence: set `--args` on the job, start it, poll the execution, print the container logs, and
**restore the scheduled arguments in an `always()` step**. That last part is the reason it is a
workflow and not a note in a document: `--args` cannot be passed to `job start`
([azure-cli#27521](https://github.com/Azure/azure-cli/issues/27521),
[azure-container-apps#1360](https://github.com/microsoft/azure-container-apps/issues/1360)), so a
manual run must mutate the definition the quarterly cron reads, and a run that is cancelled
before its restore leaves the schedule pointed at `version` until someone notices. It restores
from `infra/main.bicep`, not from whatever the live job was holding, so a job already left
mutated gets corrected rather than preserved.
*What the user still has to do:* dispatch it, and read the result. A session can trigger a
workflow and read its logs, so once it is on `main` this is closed both ways.

---
## Known unknowns the user may want to act on (not blocking)

1. **Is the Missoula drop list a standing rule or a monthly judgement?** One period of evidence,
   four properties, perfectly consistent. A second period will settle it. Until then the drop
   list in `config/outputs/missoula-investor-report.yaml` is treated as a rule.
2. **Can McCathren deliver a digital export instead of scans?** Removes the OCR stage and its
   error floor. Worth asking them.
3. **Is 128 S. 5th Street West going dormant?** Zero units, YTD income down 79 % year on year.
   If the record is retired, remove it from `records` in `config/properties.yaml`; WayPointe then
   builds as a single-record package. (Leaving it in place would produce `missing_required`.)
4. **Cornerstone's own components** arrive as three separate one-page PDFs. If Cornerstone ever
   exports them as one file, `cornerstone-qbo` needs `cardinality`/segmentation like a PM source.
   Nothing in the design prevents that; it just isn't built.
