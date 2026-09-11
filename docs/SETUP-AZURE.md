# Setting up Azure

End-to-end setup for running the quarterly build as an **Azure Container Apps Job**. Follow it
top to bottom once; after that a deploy is one click in GitHub Actions.

**Prefer clicking to typing?** [`SETUP-AZURE-PORTAL.md`](SETUP-AZURE-PORTAL.md) is the same
setup done in the Azure portal, with the three unavoidable commands run in Cloud Shell. Follow
one document or the other, not both.

**What you need before starting:** an Azure subscription where you are Owner (or Contributor
plus User Access Administrator) on at least one resource group, and the Azure CLI installed
(`az version` — get it from <https://learn.microsoft.com/cli/azure/install-azure-cli>).

**Roughly what it costs.** The job only bills while it runs — minutes, four times a year — so
compute is effectively free. The two standing costs are Log Analytics ingestion (pennies at this
volume) and the Container Apps Environment. Expect single-digit dollars a month, dominated by
whatever else lives in the environment.

---

## What gets created

| Resource | Why |
|---|---|
| Resource group | holds everything, so deleting it removes everything |
| Key Vault + 2 secrets | the Anthropic key and the Google service account, referenced by the job — never baked into the image or the template |
| Log Analytics workspace | where the job's output goes, 90-day retention |
| Container Apps Environment | the compute the job runs in |
| Container Apps Job | the runner itself: quarterly schedule, 2 vCPU / 4 GiB, 1 h timeout, 1 retry |
| Service principal | how GitHub Actions signs in to deploy |

`infra/main.bicep` creates the bottom four. The top two and the service principal are created
once by `infra/bootstrap.sh`, because they hold secrets and grant access — things worth doing
deliberately rather than in a pipeline.

---

## Step 1 — Sign in and pick the subscription

```bash
az login
az account show --output table          # is this the right subscription?
az account set --subscription "<name or id>"    # if not
```

## Step 2 — Run the bootstrap script

From the repository root:

```bash
./infra/bootstrap.sh
```

It will:

1. confirm the subscription with you before doing anything;
2. register the `Microsoft.App`, `Microsoft.OperationalInsights` and `Microsoft.KeyVault`
   resource providers (first time on a subscription this can take a few minutes);
3. create the resource group `rg-cust-cornerstone` in `westus2` (West US 2);
4. create the Key Vault `crr-kv-accounting` with RBAC authorisation;
5. grant *you* `Key Vault Secrets Officer` on it, then wait 30 seconds for that to take effect;
6. **prompt you for the Anthropic API key** (typed, not echoed) and **the path to the Google
   service-account JSON**, and store both as vault secrets;
7. create the `crr-github-actions` service principal, scoped to that one resource group;
8. print the exact values to paste into GitHub.

To change the defaults, set them first:

```bash
RESOURCE_GROUP=my-rg LOCATION=eastus2 ./infra/bootstrap.sh
```

**Keep that terminal open** — the last block it prints contains a credential shown only once.

### If you would rather do it by hand

The script is not magic. The equivalent commands:

```bash
az group create --name rg-cust-cornerstone --location westus2

az keyvault create --name crr-kv-accounting --resource-group rg-cust-cornerstone \
  --location westus2 --enable-rbac-authorization true

# Grant yourself data-plane access — being subscription Owner is not enough for RBAC vaults.
az role assignment create --assignee-object-id "$(az ad signed-in-user show --query id -o tsv)" \
  --assignee-principal-type User --role "Key Vault Secrets Officer" \
  --scope "$(az keyvault show -n crr-kv-accounting --query id -o tsv)"

az keyvault secret set --vault-name crr-kv-accounting --name anthropic-api-key --value "sk-ant-..."
az keyvault secret set --vault-name crr-kv-accounting --name google-service-account-b64 \
  --value "$(base64 -w0 service-account.json)"

az ad sp create-for-rbac --name crr-github-actions --role Contributor \
  --scopes "/subscriptions/<sub-id>/resourceGroups/rg-cust-cornerstone" --json-auth
```

## Step 3 — Put the values into GitHub

<https://github.com/arcticbio/cornerstone.accounting.reports/settings/secrets/actions>

**Secrets** tab → **New repository secret**:

| Name | Value |
|---|---|
| `AZURE_CREDENTIALS` | the entire JSON block the script printed, `{` to `}` inclusive |

**Variables** tab → **New repository variable**:

| Name | Value |
|---|---|
| `AZURE_RESOURCE_GROUP` | `rg-cust-cornerstone` |
| `AZURE_KEY_VAULT_NAME` | `crr-kv-accounting` |

While you are there, confirm the runtime secrets from `docs/SETUP-CREDENTIALS.md` are also set:
`ANTHROPIC_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_B64` (Secrets) and `CRR_GDRIVE_ROOT_FOLDER_ID`
(Variables). The deploy workflow reads the Drive folder id from that variable.

## Step 4 — Decide how Azure pulls the image

The image lives at `ghcr.io/arcticbio/crr`. Packages from a private repository are private by
default, and **Azure cannot pull a private image without credentials**. Pick one:

**Option A — make the package public (simplest).** The image contains only code, config and the
golden labels; no tenant data ever enters it, and CI fails the build if `data/` appears inside.

1. <https://github.com/arcticbio?tab=packages> → the **crr** package
2. **Package settings** → **Danger Zone** → **Change visibility** → **Public**

**Option B — keep it private and give Azure a pull token.**

1. <https://github.com/settings/tokens> → **Generate new token (classic)**
2. Scope: **`read:packages`** only. Set an expiry you will remember to rotate.
3. In the repository's Actions **Secrets**, add:
   - `GHCR_PULL_USERNAME` = your GitHub username
   - `GHCR_PULL_TOKEN` = the token
4. The deploy workflow passes them through automatically when they exist.

## Step 5 — Preview the deployment

1. **Actions** → **Deploy to Azure** → **Run workflow**
2. Leave **Preview the changes without applying them** ticked.
3. Run it.

The **What-if** step prints what Azure would create — expect four `+ Create` entries. Nothing has
changed yet. If it fails here, read the error: a missing variable names itself, and a sign-in
failure means `AZURE_CREDENTIALS` was pasted incompletely.

## Step 6 — Deploy

Run it again with **Preview** *unticked*. The workflow will:

1. compile the template;
2. deploy the four resources;
3. try to grant the job's managed identity `Key Vault Secrets User` on the vault.

That last step needs User Access Administrator on the vault. If the service principal does not
have it, the step is marked as failed-but-continued and the run prints the exact command to run
yourself. **This is expected and not a problem** — run the command it prints, then re-run the
workflow so the job picks the secrets up.

The workflow checks Azure before it warns: if the job's identity can already read the vault —
because you, or an earlier run, granted it — the step reports that and stays quiet. A warning
therefore means the access really is missing, not merely that this run could not create it.

Why it cannot be part of the template: the job's identity does not exist until the job does.

## Step 7 — Smoke test

Two runs that touch neither Drive nor the model. **`--args` does not work on `job start`** —
it fails with `ContainerAppImageRequired`, and adding `--image` drops the job's environment
variables ([azure-cli#27521](https://github.com/Azure/azure-cli/issues/27521)); `--args` is also
reported as ignored there
([azure-container-apps#1360](https://github.com/microsoft/azure-container-apps/issues/1360)).
Set the arguments on the job instead, run it, then put them back:

```bash
az containerapp job update --name crr-quarterly --resource-group rg-cust-cornerstone --args "version"
az containerapp job start  --name crr-quarterly --resource-group rg-cust-cornerstone

az containerapp job update --name crr-quarterly --resource-group rg-cust-cornerstone --args "validate-config"
az containerapp job start  --name crr-quarterly --resource-group rg-cust-cornerstone
```

**Restore the arguments when you are done** — the quarterly schedule runs whatever is
configured. Re-running the deploy workflow resets them from `infra/main.bicep`.

Watch them:

```bash
az containerapp job execution list --name crr-quarterly --resource-group rg-cust-cornerstone --output table
az containerapp job logs show --name crr-quarterly --resource-group rg-cust-cornerstone --follow
```

`version` should print `crr 1.0.0` and exit 0. `validate-config` should list 4 schemas,
3 output definitions and 8 properties. If `version` works and `validate-config` does not, the
image is fine and the config copy is not — which would be a bug worth reporting.

## Step 8 — A real run

Only once a period's inputs are in Drive (`docs/RUNBOOK.md` → *Preparing a period in Drive*):

```bash
# The period just ended — what the schedule does, and the only form needing no arguments.
az containerapp job start --name crr-quarterly --resource-group rg-cust-cornerstone
```

For any *other* period or a single property, use **Actions → Build a period**: it takes the
period, property, repo and classifier as inputs, runs the same image with the same secrets, and
does not require mutating the job definition the schedule depends on.

**Read the exit code carefully.** The runner's contract (SPEC §6.8) is 0 built, 2 needs review,
1 failed — and Azure marks any non-zero exit as a *failed execution*. **An execution showing
"Failed" is very often exit code 2, which means the packages built but one or more went to
`review/` for a human.** Check the logs before treating it as an incident; the packages and
manifests are in Drive either way.

## Step 9 — Turn the schedule on

The job deploys with the quarterly cron already armed: `0 6 20 1,4,7,10 *` — 06:00 UTC on the
20th of January, April, July and October, which closes December, March, June and September. The
runner defaults `--period` to the month just ended, so a scheduled run needs no argument.

To deploy the job *without* arming the schedule, untick **Arm the quarterly cron** when you run
the deploy workflow. That parks the cron on 31 February, which never arrives; manual starts
still work. Re-run with it ticked when you are ready.

---

## Keeping it running

**New image.** The job pins a tag, not a digest, so pushing a new `:build-v1` is enough — the
next execution pulls it. To pin a release instead, run the deploy workflow with
`image = ghcr.io/arcticbio/crr:v1.0.0`.

**Rotating a key.** Update the vault secret; the job reads it on the next execution.

```bash
az keyvault secret set --vault-name <vault> --name anthropic-api-key --value "sk-ant-new..."
```

Remember the GitHub Actions copy is separate (`docs/SETUP-CREDENTIALS.md`).

**Where the logs are.** Azure portal → the resource group → `crr-logs` → Logs, or:

```bash
az containerapp job logs show --name crr-quarterly --resource-group rg-cust-cornerstone --follow
```

Every line is JSON. Page text, tenant names, file paths and secrets are never logged — only
document hashes, page counts and status.

**Tearing it down.** `az group delete --name rg-cust-cornerstone --yes` removes everything created here.
Nothing in Drive or GitHub is touched.

---

## Hardening: OIDC instead of a stored credential

`AZURE_CREDENTIALS` is a long-lived secret. Federated credentials (OIDC) remove it: GitHub
proves its identity per-run and Azure issues a short-lived token. Worth doing if this becomes
more than a quarterly job.

```bash
az ad app federated-credential create --id <app-id> --parameters '{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:arcticbio/cornerstone.accounting.reports:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

Then in `.github/workflows/deploy.yml`: add `permissions: id-token: write`, and replace the
`creds:` input to `azure/login@v2` with `client-id`, `tenant-id` and `subscription-id`. Once
that works, delete the `AZURE_CREDENTIALS` secret and reset the service principal's password.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Deploy fails: `MissingSubscriptionRegistration` | resource provider not registered | `az provider register -n Microsoft.App --wait` |
| Deploy fails: `AuthorizationFailed` | the service principal is not Contributor on the group | re-check the `--scopes` used in step 2 |
| Deploy fails at sign-in: `AADSTS7000215` | the `clientSecret` in `AZURE_CREDENTIALS` is not the secret's **Value** — usually the portal's **Secret ID** pasted by mistake | make a new client secret and copy the **Value** column; see `SETUP-AZURE-PORTAL.md` §1.7 |
| Deploy fails at sign-in: `AADSTS7000222` | the client secret expired | issue a new one and update `AZURE_CREDENTIALS` |
| Secret step in bootstrap fails: `Forbidden` | RBAC vault data-plane role not yet effective | wait a minute and retry; the role takes time to propagate |
| Job execution fails immediately, logs mention the secret | the job's identity cannot read the vault | step 6's role assignment; then re-run the deploy |
| Job execution fails: `UNAUTHORIZED` / manifest unknown | private GHCR image, no pull credentials | step 4 |
| Execution shows "Failed", logs end with review reasons | **exit code 2 — packages need review** | this is normal; work the review queue per `docs/RUNBOOK.md` |
| `crr version` works, real build fails at the classifier | the Anthropic key in the vault is wrong or expired | reset the vault secret |
