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

**B-01 · `ANTHROPIC_API_KEY` is not set in the build environment.**
*Blocked:* the Phase 3 smoke run against the real model (accuracy and token counts on the Fort
Grounds PM source), the Phase 3 `api`-marked integration tests, and the Phase 5 real-model eval
and build (`crr eval --classifier anthropic`, `crr build --classifier anthropic`).
*What continues:* everything else. The classifier itself is built and unit-tested against a fake
client — message construction, the cached prefixes, forced tool, retries, the repair round, the
refusal path and token accounting. `GoldenClassifier` drives the whole pipeline end to end, so
Phases 4, 6, 7, 8 and 9 are unaffected. The moment the key is set, `uv run pytest -m api` and
`uv run crr eval --classifier anthropic` are the two commands that close this out.

**B-02 · ~~GitHub Actions has not run CI on PR #1.~~ RESOLVED 2026-09-10.**
Earlier runs were cancelled by the workflow's own concurrency group as commits landed in quick
succession, not stalled for want of a runner. Run
[34462978204](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34462978204)
is green on all three jobs: lint/types/tests/validate-config/eval gate, the Bicep compile, and
the image job.

**B-03 · ~~No container runtime in the build environment.~~ RESOLVED 2026-09-10 in CI.**
Still true locally — `/var/run/docker.sock` does not exist here — but CI's `image` job now
builds the image, runs `crr version`, proves `/app/data` is absent, checks all three OCR
binaries inside the container, runs the golden build there, and pushes to GHCR. All green.

**B-05 · The `v1.0.0` tag cannot be pushed from this session.**
*Needed:* one command from someone with push rights on refs other than the session branch. The
annotated tag exists locally on `c34c69b`; `git push origin v1.0.0` returns `HTTP 403`, because
cloud sessions may push only their own branch (D-15). *Blocked:* only the tag, and with it the
`:latest` / `:v1.0.0` GHCR images, which the CI workflow publishes on a `v*` tag.
*What continues:* everything else; `:build-v1` and `:sha-<short>` are already published.
After merging PR #1:

```
git tag -a v1.0.0 -m "Cornerstone Report Runner v1.0.0" && git push origin v1.0.0
```

**B-06 · CI on this org's runners is intermittently very slow, and the final commit's run has
not finished.**
*What was seen:* run
[34462978204](https://github.com/arcticbio/cornerstone.accounting.reports/actions/runs/34462978204)
(commit `1beaf40`, Phase 8) went green on all three jobs in under four minutes. The run for the
Phase 9 commits then sat for half an hour with the `Tests` step and the in-container golden
build both started and neither progressing, while the 16-second Bicep job on the same run
finished normally. Earlier in the session several runs queued without starting and were
cancelled by the workflow's concurrency group.
*What this does and does not mean:* the same tree passes the identical gate locally — ruff,
`mypy src`, **375 passed / 5 skipped**, 94 % coverage, `crr validate-config`, `crr eval
--classifier golden --gate` — and the previous commit's tree passed all three CI jobs including
the in-container build and the GHCR push. So this reads as runner capacity, not a defect. It is
recorded rather than assumed: **re-run the workflow and confirm it goes green before merging.**

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
