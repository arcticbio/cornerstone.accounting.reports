# Credentials setup

How each secret reaches the code, per environment. Read this before debugging a "key not set"
message — one of these variables behaves differently from the rest.

## The one surprise: `ANTHROPIC_API_KEY` is reserved on Claude Code for the web

Claude Code on the web authenticates its *own* model calls through the user's Anthropic account,
not through an environment variable. The name `ANTHROPIC_API_KEY` is therefore reserved: you can
type it into the cloud-environment editor, and it is saved, but it is **stripped before the
session container starts**. The editor states this directly under the variables box:

> "ANTHROPIC_API_KEY" won't be used to authenticate requests. Claude Code sessions are
> authenticated through your Anthropic account.

This is not a propagation delay and it is not fixed by starting a new session. Confirmed in a
session where `CRR_MODEL`, `CRR_GDRIVE_ROOT_FOLDER_ID` and `GOOGLE_SERVICE_ACCOUNT_B64` all
arrived from the same environment while `ANTHROPIC_API_KEY` was empty.

`crr` needs its own key because the pipeline classifier is an ordinary API client — it is not the
session's model call and cannot borrow the session's account auth.

**Use `CRR_ANTHROPIC_API_KEY` instead.** The `CRR_` prefix is not reserved and passes through
untouched, as the other `CRR_` variables demonstrate.

## Variable by environment

| Variable | Cloud session (web) | Local shell / `.env` | GitHub Actions | Azure |
|---|---|---|---|---|
| `CRR_ANTHROPIC_API_KEY` | **use this** — set in the cloud-environment editor | works | works (repo secret) | works (Key Vault) |
| `ANTHROPIC_API_KEY` | stripped; never arrives | works (fallback) | works (fallback) | works (fallback) |
| `GOOGLE_SERVICE_ACCOUNT_B64` | works | works | repo secret | Key Vault |
| `CRR_GDRIVE_ROOT_FOLDER_ID` | works | works | repo variable | app setting |
| `CRR_MODEL` | works | works | repo variable | app setting |

`settings.py` reads the classifier key from `CRR_ANTHROPIC_API_KEY` first and falls back to
`ANTHROPIC_API_KEY`, so a local `.env` or a CI secret under the conventional name keeps working:

```python
anthropic_api_key: SecretStr | None = Field(
    default=None,
    validation_alias=AliasChoices("CRR_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
)
```

## Handling of the key itself

The cloud-environment editor warns that its variables "are visible to anyone using this
environment". Treat any key pasted there as shared with everyone who can open the environment,
and rotate it at <https://console.anthropic.com/settings/keys> if that is wider than intended or
if the value has been shown in a screenshot or a chat. Nothing in this repo prints or commits the
key: `.env` is gitignored, and the logging rule in `CLAUDE.md` forbids logging secrets.

## Verifying

Start a **new** session after editing the environment — variables are injected at container start,
so a running session keeps the values it booted with. Then:

```bash
scripts/session_start.sh          # should print "CRR_ANTHROPIC_API_KEY: set (classifier live)"
printenv | grep -c CRR_ANTHROPIC_API_KEY   # 1
```

If the hook still says "not set", the value did not reach the container. Check the variable name
character by character in the editor, and confirm you are editing the same environment the
session runs in (its name appears in the session header — `cornerstone-reports`).

## Degraded behaviour without a key

Per `PLAN.md`, no phase blocks on this. The classifier falls back to `--classifier golden`
(the checked-in labels in `eval/golden/`), the live smoke run and the `api`-marked integration
tests are skipped, and everything else — assembly, composition, eval against golden, Drive —
runs normally.
