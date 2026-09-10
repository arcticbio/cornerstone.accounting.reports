# Handoff — launching the autonomous build

> **Historical.** This document launched the v1 build, which is finished, merged and tagged
> `v1.0.0`. Its `build/v1` branch names and "what to expect while you are away" timings describe
> that first run; they are not instructions for picking the work up now. For the current state
> and what is open, read the "Pick up here" block at the top of `PROGRESS.md`.

This is the human runbook. It gets the build started in Claude Code on the web and tells you
what to expect while you are away. Everything Claude Code needs is in this repository; the only
things it cannot produce itself are the two API keys.

Time to complete this page: about 30 minutes, most of it in Google Cloud Console.

---

## 1. Put the handoff files in the repository

Copy the contents of this package to the **root** of `arcticbio/cornerstone.accounting.reports`
(not inside `Report Assembly Bundle/`). You should end up with these at the root, beside the
existing `Report Assembly Bundle/` folder:

```
CLAUDE.md  HANDOFF.md  PROGRESS.md  .gitignore  .claude/  config/  docs/  eval/  scripts/
```

Commit and push to `main`. Claude Code's first task (Phase 0) moves the bundle to
`data/bundle/2026-06/` and removes the stray `.DS_Store` files — you do not need to.

---

## 2. Get the two keys

### Anthropic API key (required for the classifier)

Your Max plan does **not** include API access; the pipeline calls the API directly and is billed
separately. Expect roughly $5 per quarterly run, and perhaps $20–40 during the build itself for
evals and smoke tests.

1. Go to <https://console.anthropic.com> → sign in with the same account → **API Keys** →
   **Create Key** → name it `crr-build`.
2. Under **Billing**, add a payment method or credits. Set a monthly spend limit if you like
   ($50 is generous).
3. Copy the key (`sk-ant-…`). You will paste it once in step 3 and never need it again.

### Google service account (required for Drive; can be added later)

The runner reads inputs from, and publishes outputs to, a Google Drive folder you own, using a
service account — a robot identity you share the folder with.

1. <https://console.cloud.google.com> → project dropdown → **New project** → name
   `cornerstone-reports` → Create. Make sure it is selected.
2. **APIs & Services → Library** → search **Google Drive API** → Enable.
3. **IAM & Admin → Service Accounts → Create service account** → name `crr-runner` →
   Create and continue → skip the role steps → Done.
4. Open the service account → **Keys** → **Add key → Create new key → JSON** → Create. A file
   downloads. Note the account's email; it looks like
   `crr-runner@cornerstone-reports.iam.gserviceaccount.com`.
5. In **Google Drive**, create a folder named `Cornerstone Reports`. Right-click → **Share** →
   paste the service-account email → role **Editor** → uncheck "Notify" → Share.
6. Open the folder; the URL ends in `/folders/<long id>`. Copy that id.
7. Convert the JSON key to one line of base64 so it fits an environment variable. On a Mac:
   ```
   base64 -i ~/Downloads/cornerstone-reports-XXXX.json | tr -d '\n' | pbcopy
   ```
   That puts the value on your clipboard. Delete the downloaded JSON afterwards.

If you skip this for now, the build still completes; Phase 6 uses a fake Drive and leaves a
checkpoint asking for these two values.

---

## 3. Create the cloud environment

1. Go to <https://claude.ai/code>. Complete onboarding if prompted: authorise the Claude GitHub
   App and make sure it can see `arcticbio/cornerstone.accounting.reports`.
2. In the row above the message box, click the **cloud icon** (it shows the current
   environment's name, probably `Default`) → **Add cloud environment**.
3. Fill in:

   **Name:** `cornerstone-reports`

   **Network access:** `Trusted` (the default). It already covers `api.anthropic.com`,
   `*.googleapis.com`, `accounts.google.com`, PyPI, GitHub and Docker Hub. Nothing else is needed.

   **Environment variables** (one per line):
   ```
   CRR_ANTHROPIC_API_KEY=sk-ant-…   # not ANTHROPIC_API_KEY — see docs/SETUP-CREDENTIALS.md
   GOOGLE_SERVICE_ACCOUNT_B64=…paste from clipboard…
   CRR_GDRIVE_ROOT_FOLDER_ID=…the folder id…
   CRR_MODEL=claude-opus-5
   ```
   Leave the two Google lines out if you skipped section 2b. (These variables are visible to any
   session in this environment. That is only you. The separate "API credentials" feature in the
   dialog does not apply here — Anthropic's proxy never attaches it to `api.anthropic.com`, and
   Google's service-account flow is not a static bearer token.)

   **Setup script:**
   ```bash
   #!/bin/bash
   apt-get update -qq
   apt-get install -y -qq tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd ocrmypdf ghostscript || true
   ```

4. **Create environment.** The first session builds a cached snapshot with those packages
   installed; later sessions start from it.

---

## 4. Start the build

1. Still at <https://claude.ai/code>, select the repository
   `arcticbio/cornerstone.accounting.reports`, branch `main`.
2. Make sure the environment selector shows `cornerstone-reports`.
3. Set the **permission mode** dropdown to **Auto**. (On Max this is the default. It lets
   Claude edit, run, and push without asking, with background safety checks.)
4. Paste this as the first message:

   ```
   Build the Cornerstone Report Runner end to end. Start by reading CLAUDE.md, then PROGRESS.md,
   then docs/PLAN.md, then docs/SPEC.md. Work through every phase of docs/PLAN.md on branch
   build/v1, following the operating loop exactly: implement with tests, keep lint/type/test
   green, tick PROGRESS.md, commit and push after every task. Open the PR in Phase 0 and keep its
   description current. Stop only at the checkpoints PLAN.md marks STOP; at any other blocker,
   record it in docs/QUESTIONS.md and continue with the next unblocked task. I will be offline
   for long stretches — do not wait for me unless PLAN.md says to.
   ```

5. Send it. You can close the browser. The session keeps running.

---

## 5. What happens next, and what you will see

- Within the first hour: a branch `build/v1` and a PR titled **Cornerstone Report Runner v1**
  with a phase table. CI runs on every push.
- Progress is always readable in `PROGRESS.md` on the `build/v1` branch and in the PR
  description — no need to open the session to know where things are.
- The session shows up in the **Claude mobile app** under Code. You can read the transcript,
  answer questions, or send a nudge ("continue") from your phone.

**Checkpoints.** Claude Code stops and waits at exactly two planned points, and its last message
will begin with `CHECKPOINT:`:

| When | What it asks |
|---|---|
| End of Phase 7 | Whether to proceed to Azure (needs `AZURE_CREDENTIALS`, a subscription and resource group) or stay on GitHub Actions. **Replying "GitHub Actions is fine, skip Phase 8" is a complete answer.** |
| End of Phase 9 | Nothing — it is the completion report with eval numbers, cost per run and the PR link. |

It may also stop early at Phase 5 if the classifier cannot reach 95 % on one manager after three
prompt iterations, with a confusion analysis and a proposed fix for you to approve.

Anything else it needs — a missing key, an unclear spec — it writes to `docs/QUESTIONS.md`
under **Blocked** and keeps going on other work. Check that file when you check in.

**If the session has stopped.** Cloud sessions expire after a period of inactivity, including
while waiting for you at a checkpoint. Open the session at claude.ai/code and send `continue`
(or your answer); the conversation history is restored and it resumes from `PROGRESS.md`. If a
session was reclaimed mid-task, the next one picks up from the last commit — that is why the
plan insists on small commits.

**Usage limits.** Cloud sessions draw on your Max plan's rate limits. A multi-hour autonomous
build is heavy usage; if it pauses on a limit, it resumes when the window resets. Nothing is lost.

---

## 6. Merging and running

- **Merge the PR** when Phase 9 reports complete (or earlier, per phase, if you prefer). Squash
  or merge-commit, your choice; nothing depends on it.
- **First real run:** add repo secrets `ANTHROPIC_API_KEY` and `GOOGLE_SERVICE_ACCOUNT_B64`
  and repo variable `CRR_GDRIVE_ROOT_FOLDER_ID` under GitHub → Settings → Secrets and
  variables → Actions. Place a period's inputs in Drive per `docs/RUNBOOK.md`, then run the
  **Build period** workflow from the Actions tab with the period id. Outputs land in Drive under
  each property's `output/` (or `review/` if anything needs a look).
- **Azure**, when you want it: provide the credentials at the Phase 7 checkpoint, or later by
  starting a new session with "Execute Phase 8 of docs/PLAN.md".

---

## 7. If something goes wrong

| Symptom | What to do |
|---|---|
| Session says it cannot reach `api.anthropic.com` for the pipeline | The classifier key is not set. Set **`CRR_ANTHROPIC_API_KEY`** in the cloud environment and start a new session — the unprefixed `ANTHROPIC_API_KEY` is reserved by Claude Code on the web and stripped from the container, so setting that name has no effect. `docs/SETUP-CREDENTIALS.md`. |
| `tesseract missing` in the session-start output | The setup script did not run or failed. Edit the environment's setup script (any change rebuilds the cache) and start a new session. |
| PR CI is red and the session is idle | Send `CI is failing on build/v1 — fix it and continue with PLAN.md` |
| It asks something you have already decided | Point it at `docs/DECISIONS.md` by id, e.g. "See D-03. Continue." |
| You want to change scope | Edit `docs/PLAN.md` or `docs/SPEC.md` on `build/v1`, commit, and tell the session "Re-read PLAN.md, it changed." |

---

## What you are not being asked to do

You do not need to write code, review every commit, or answer design questions the spec already
settles. The package was written so that a competent engineer — human or otherwise — can build
this without you. Your two jobs are the keys and the two checkpoints.
