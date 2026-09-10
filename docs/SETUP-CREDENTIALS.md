# Setting the credentials

Three secrets make the runner work. This says exactly where each one goes, and — importantly —
**which copy does what**. Setting a key in one place does not set it in the others; they are
separate systems that never see each other's configuration.

| Secret | What it is for |
|---|---|
| `CRR_ANTHROPIC_API_KEY` | the page classifier. Without it the runner can only replay the June golden labels. `ANTHROPIC_API_KEY` is read as a fallback everywhere except Claude Code on the web, which reserves that name — see below |
| `GOOGLE_SERVICE_ACCOUNT_B64` | reading inputs from Drive and publishing packages back |
| `CRR_GDRIVE_ROOT_FOLDER_ID` | which Drive folder holds the manager folders. **Not a secret** — a variable |

---

## The Anthropic API key: the four places it can live

You asked where to set it. The honest answer is that it depends on *which* of these you want to
work, and they are independent:

| # | Where | Makes this work | Needed for production? |
|---|---|---|---|
| 1 | **GitHub Actions repository secret** | `Build a period` workflow runs a real build | **Yes — this is the one that matters** |
| 2 | **Azure Key Vault secret** | the scheduled Container Apps Job | Yes, once Azure is deployed |
| 3 | **Claude Code cloud environment variable** — must be named `CRR_ANTHROPIC_API_KEY` | Claude running `crr eval --classifier anthropic` in a session | No — development only |
| 4 | Your own shell / `.env` | running `crr` on your laptop | No — optional |

Do **1** now. Do **2** when you deploy Azure (`docs/SETUP-AZURE.md` step 4 covers it). **3** is
only so Claude can measure real-model accuracy for you; nothing in production depends on it.

### 1. GitHub Actions repository secret — do this one

1. Go to <https://github.com/arcticbio/cornerstone.accounting.reports/settings/secrets/actions>.
2. Click **New repository secret**.
3. **Name:** `ANTHROPIC_API_KEY` — exactly this, case-sensitive.
4. **Secret:** paste the key (it starts `sk-ant-`). No quotes, no trailing newline or space.
5. Click **Add secret**.

While you are on that page, check the other two are there as well:

- **Secrets** tab: `ANTHROPIC_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_B64`
- **Variables** tab: `CRR_GDRIVE_ROOT_FOLDER_ID` = `1_tUMelVG8trnjPmJWul0YXo23VgWgdSc`

The variable goes on the **Variables** tab, not Secrets — the workflow reads it as
`vars.CRR_GDRIVE_ROOT_FOLDER_ID`. A folder id is not sensitive and putting it in Secrets only
makes it invisible when you are trying to check it.

**Verify it works** without spending anything on a full run:

1. **Actions** → **Build a period** → **Run workflow**
2. period `2026-06`, property `fort-grounds`, repo `local`, classifier `anthropic`
3. Run it. That builds one property from the June bundle in the repo using the real model — a
   handful of API calls, roughly a dollar. A green tick means the key is wired correctly.

### 3. The Claude Code cloud environment — what I actually see

You said the key is already set in the Claude Code cloud environment, and it was — under the
name `ANTHROPIC_API_KEY`. That name does not work here, and no amount of restarting fixes it.

**Claude Code on the web reserves `ANTHROPIC_API_KEY`.** Sessions authenticate their own model
calls through your Anthropic account, so the platform strips that variable before the session
container starts. The cloud-environment editor says so itself, under the variables box:

> "ANTHROPIC_API_KEY" won't be used to authenticate requests. Claude Code sessions are
> authenticated through your Anthropic account.

It is saved in the editor and it never arrives. This was misdiagnosed once as an injection-timing
problem — variables *are* injected at container start, so that is a real effect, just not this
one. The evidence that separates them: `CRR_MODEL`, `CRR_GDRIVE_ROOT_FOLDER_ID` and
`GOOGLE_SERVICE_ACCOUNT_B64` all arrive from the same environment in the same session while
`ANTHROPIC_API_KEY` is empty. One name is filtered, not the whole environment.

`crr` needs a key of its own because the classifier is an ordinary API client — it is not the
session's model call and cannot borrow the session's account auth.

**Use `CRR_ANTHROPIC_API_KEY`.** The `CRR_` prefix is not reserved and passes through untouched.
`settings.py` reads that name first and falls back to `ANTHROPIC_API_KEY`, so places 1, 2 and 4
in the table above are unaffected — GitHub Actions and Azure keep the conventional name, and the
`build-period` workflow still passes `secrets.ANTHROPIC_API_KEY`.

To fix it:

1. Open <https://claude.ai/code> → **Environments** → the **`cornerstone-reports`** environment
   (the one named in this session's header — if you have more than one, it must be this one).
2. Rename the variable to `CRR_ANTHROPIC_API_KEY`, exactly, case-sensitive. Same value; no
   surrounding quotes or whitespace.
3. **Start a new Claude Code session.** Variables are injected at container start, so a running
   session keeps the values it booted with — this part of the original advice was right.
4. The session-start banner then reads `CRR_ANTHROPIC_API_KEY: set (classifier live)`.

One caution about that box: the editor warns its variables "are visible to anyone using this
environment", and it is not a secret store. Treat a key pasted there as shared with everyone who
can open the environment, and prefer a key you are willing to rotate.

In that new session, ask Claude to close out B-01 — it is two commands:

```bash
uv run pytest -m api                       # one real classification per manager
uv run crr eval --classifier anthropic --gate   # scores all 31 documents, writes the report
```

That is a full-bundle eval: ~172 API calls, an estimated ~$10. The report lands in
`eval/reports/` and gets committed, which is what turns the modelled cost estimate in
`PROGRESS.md` into a measured one.

---

## `GOOGLE_SERVICE_ACCOUNT_B64` — already working, for reference

This is the base64 of a Google service-account JSON key, on one line. It is already set in the
Claude Code environment and verified live: the runner can list your Drive root and created the
`2026-09 September` folder skeleton for all eight properties.

If you ever need to regenerate it:

```bash
base64 -w0 service-account.json          # Linux
base64 -i service-account.json | tr -d '\n'   # macOS
```

The service account needs **Editor** on the one shared root folder and nothing else. It reads
`inputs/` and writes `output/` and `review/`; it never deletes and never overwrites.

---

## Rotating a key

1. Create the new key at the provider.
2. Update every copy from the table above that you have set — they do not sync.
3. Run the one-property verification build.
4. Revoke the old key.

The runner reads keys from the environment only. Nothing is written to disk, nothing is logged:
there is a test (`tests/unit/test_logging_hygiene.py`) that fails the build if a key, a page of
text, a tenant name or a file path ever reaches a log line.
