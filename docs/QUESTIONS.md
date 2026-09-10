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

**B-04 · Azure deployment — the user has chosen to proceed; instructions written.**
*Status 2026-09-10:* the user wants Azure and has a subscription, and is working through setup
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
