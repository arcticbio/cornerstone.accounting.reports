# Cornerstone Report Runner — instructions for Claude Code

You are building `crr`, a Python service that assembles quarterly investor report PDFs from
property-manager exports and Cornerstone's accounting components, using a vision model to
classify pages and deterministic code to compose. You are expected to build it **end to end,
autonomously**, coming back to the user only at the checkpoints defined in `docs/PLAN.md`.

## Read these first, in this order

1. `PROGRESS.md` — where the build is. Always start here.
2. `docs/PLAN.md` — phases, tasks, acceptance criteria, checkpoint rules, the operating loop.
3. `docs/SPEC.md` — the technical contract. Interfaces, formats, invariants. Authoritative.
4. `docs/DECISIONS.md` — decisions already made. Do not re-open them.
5. `docs/QUESTIONS.md` — how to record assumptions and blockers.
6. `docs/ANALYSIS-*.md` — the evidence the spec is built on. Read when a spec section feels arbitrary.

## Ground rules

- **Follow the operating loop in `PLAN.md`** for every task: read spec → implement with tests →
  lint/type/test green → tick `PROGRESS.md` → commit → push → next task.
- **Work on branch `build/v1`.** Open one PR to `main` in Phase 0 and keep its description's
  phase table current. Never force-push. Never rewrite history.
- **Never modify anything under `data/bundle/`** after the Phase 0 move. It is a fixture.
- **Never read `reference/` or `target/` folders from pipeline code.** Tests enforce this.
- **Never commit `work/`, `.env`, PDFs outside `data/bundle/`, or anything containing a key.**
- **Never log page text, image bytes, tenant names, or secrets.**
- **Prefer review over guess.** When classification or config is ambiguous, the build goes to
  `NEEDS_REVIEW`; it does not pick the likeliest answer.
- **Do not improvise around the spec.** If the spec is wrong or incomplete, write it up in
  `QUESTIONS.md`, take the safest default, and continue. Amend `SPEC.md` in the same commit if
  the fix is obvious and local; say so in the commit message.
- **Commit small and often.** Sessions can end without warning; the next one resumes from git.
- **When you stop for a checkpoint,** the last line of your message must begin with `CHECKPOINT:`
  and state precisely what you need. Then, if any task in `PLAN.md` is still unblocked, keep
  working on it in the same session — a checkpoint is a question, not a halt.

## Toolchain

Python 3.12 · `uv` · `ruff` · `mypy --strict` on `src/` · `pytest` · pydantic v2 · Typer ·
structlog · pypdf · pypdfium2 · ocrmypdf (system: tesseract-ocr, ghostscript) · anthropic SDK ·
google-api-python-client.

Run everything through `uv run ...`. The SessionStart hook runs `uv sync --frozen` and prints
the top of `PROGRESS.md`; if it reports tesseract missing, install it
(`apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd ocrmypdf ghostscript`) before Phase 1's OCR
tasks and note it in `PROGRESS.md`.

## Environment variables you may find set

`CRR_ANTHROPIC_API_KEY` (classifier), `GOOGLE_SERVICE_ACCOUNT_B64` + `CRR_GDRIVE_ROOT_FOLDER_ID`
(Drive), `CRR_MODEL`. If a key is absent, the affected phase degrades as `PLAN.md` describes;
it does not block the build.

The classifier key is **`CRR_ANTHROPIC_API_KEY`**, not `ANTHROPIC_API_KEY`: Claude Code on the web
reserves the unprefixed name for its own account auth and strips it from the session container, so
it never arrives however it is set. `ANTHROPIC_API_KEY` remains a read-only fallback for local
shells and CI. Do not "fix" a missing key by asking for the unprefixed name to be set again —
see `docs/SETUP-CREDENTIALS.md`.

## Definition of done for v1

Every acceptance criterion in `PLAN.md` met, `PROGRESS.md` fully ticked or each unticked item
listed under "Blocked" in `QUESTIONS.md`, eval report committed, tag `v1.0.0`, and a final
`CHECKPOINT: v1.0.0 complete.` message with eval numbers and cost per run.
