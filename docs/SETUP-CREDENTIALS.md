# Setting the credentials

Three secrets make the runner work. This says exactly where each one goes, and — importantly —
**which copy does what**. Setting a key in one place does not set it in the others; they are
separate systems that never see each other's configuration.

| Secret | What it is for |
|---|---|
| `ANTHROPIC_API_KEY` | the page classifier. Without it the runner can only replay the June golden labels |
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
| 3 | **Claude Code cloud environment variable** | Claude running `crr eval --classifier anthropic` in a session | No — development only |
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

You said the key is already set in the Claude Code cloud environment. **It is not reaching the
session container**: at the start of this session the hook reported

```
ANTHROPIC_API_KEY: not set (classifier phases degrade to golden)
```

and `printenv ANTHROPIC_API_KEY` is empty here, while `GOOGLE_SERVICE_ACCOUNT_B64` and
`CRR_GDRIVE_ROOT_FOLDER_ID` both arrive fine. So the two Google values are configured on the
environment this session uses, and the Anthropic one is not — or not yet.

The usual cause is timing: environment variables are injected when the session's container
starts, so a variable added afterwards is not visible to the session that is already running.

To fix it:

1. Open <https://claude.ai/code> → **Environments** → the **`cornerstone-reports`** environment
   (the one named in this session's header — if you have more than one, it must be this one).
2. Check for a variable named exactly `ANTHROPIC_API_KEY`. Add it if it is missing; if it is
   there, confirm the value has no surrounding quotes or whitespace.
3. **Start a new Claude Code session** on this repository. The variable is picked up at
   container start, so the existing session will never see it.
4. The session-start banner will then read `ANTHROPIC_API_KEY: set`.

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
