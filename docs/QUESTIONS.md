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

---

## Blocked (Claude Code appends here)

*(format: `B-nn · <what is needed> · <what is blocked> · <what continues meanwhile>`)*

**B-01 · `ANTHROPIC_API_KEY` does not reach the Claude Code session container.**
*Status 2026-09-10 (later):* **the Actions half is closed.** The repository secret
`ANTHROPIC_API_KEY` reaches the container and the classifier authenticates — run
[34524350634](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34524350634)
got a 400 on the tool schema (B-07), not a 401. What remains blocked is only the part that needs
the key *in a session container*: `pytest -m api` and a local `crr eval --classifier anthropic`.
Both run in Actions instead.
*Status 2026-09-10:* the user has the key and is setting it for GitHub Actions (production).
This session still reports `ANTHROPIC_API_KEY: not set`, and `GOOGLE_SERVICE_ACCOUNT_B64` /
`CRR_GDRIVE_ROOT_FOLDER_ID` both arrive — so the variable is not on the environment this session
uses, or was added after the container started. Environment variables are injected at container
start, so a **new session** is what picks it up. See `docs/SETUP-CREDENTIALS.md`.
*Blocked:* the Phase 3 real-model smoke run, the `api`-marked integration tests, and the Phase 5
real-model eval and build. *What continues:* everything else — the classifier is unit-tested
against a fake client, and `GoldenClassifier` drives the whole pipeline end to end.
*Two commands close it out* in a session that can see the key:

```
uv run pytest -m api
uv run crr eval --classifier anthropic --gate
```

**B-08 · Both McCathren properties go to review on `cardinality_violation` with the real model.**
*Found 2026-09-10* by the first full keyed run, dispatch
[34527782436](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34527782436):
six of eight built, Timber Place and River Falls went to `review/`. Both resolved to their exact
golden page count (25 and 29), so no page was misplaced — `segment.done` counted one more run
than there are section ids (12 across 11 on Timber Place, 11 across 10 on River Falls), meaning a
`cardinality: one` section was split into two runs by a page that continues a section being
labelled as starting a new one. Confidence was 0.95–0.98 throughout and nothing came back
`unknown`, so the split is a continuation call, not an uncertain page.
*This is the gate working as specified* (D-12): it declined to publish a segmentation it could
not prove, rather than guessing. It is not a build failure and exit code 2 is the contract.
*Open:* which section and which page, in each package's `REVIEW.md` inside the run's manifests
artifact — `is_continuation` is not in the per-page log line, so the run log alone cannot say.
Both properties are the scanned, OCR'd ones, and the golden classifier builds both cleanly, so
this is a genuine model-vs-golden difference rather than a config problem.
*Next:* read the two `REVIEW.md` files; then `crr eval --classifier anthropic` to measure
continuation accuracy against the golden labels across all 31 documents. Consider logging
`is_continuation` on `classify.page` so a run log can answer this without the artifact.

**B-07 · ~~The forced tool's schema is rejected by the live API under `strict: true`.~~ RESOLVED 2026-09-10.**
*Found 2026-09-10* by the first keyed run — dispatch
[34524350634](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34524350634),
`2026-06` / `fort-grounds` / `local` / `anthropic`. Everything up to the first API call worked:
the key arrived, the four sources were fetched, all 19 pages rendered, OCR correctly skipped.
The first `POST /v1/messages` then returned **400** —
`tools.0.custom: For 'number' type, properties maximum, minimum are not supported` — from
`confidence: {"type": "number", "minimum": 0, "maximum": 1}` in `build_tool`. No fake client can
see this: the schema is only validated by the API. *Fix:* the keywords are gone; the bounds live
in the property descriptions and are enforced on parse, where `PageClassification.confidence` is
already `ge=0.0, le=1.0` and evidence already truncates at 300 — an out-of-range value now fails
the parse and sends the page to review, which is what the schema bound would have bought us.
`maxLength` on `evidence` went with it as the same class of keyword, unverified against the API
but redundant given the truncation. A unit test now walks the schema for the whole family.
*Confirmed:* `record_qualifier: {"type": ["string", "null"]}` **is** accepted under
`strict: true` — the re-run classified all 19 pages with no further schema error, so the union
type stays.
*Was blocked on* a rebuilt image: CI published to GHCR on the session branch or a `v*` tag only,
so the merge to `main` did not republish and `:build-v1` carried the defect. `BUILD_BRANCH` is
now `main`, so the merge carrying the fix republished the image (PR #3).
*Verified* by dispatch
[34526230410](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34526230410):
exit 0, `fort-grounds ok 8 pages`, no review. See "First keyed run" below.

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
