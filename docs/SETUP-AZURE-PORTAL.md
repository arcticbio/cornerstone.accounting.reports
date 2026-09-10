# Setting up Azure — the portal version

The same setup as [`SETUP-AZURE.md`](SETUP-AZURE.md), done by clicking rather than typing.
Follow **either** document, not both. If you have already run `infra/bootstrap.sh`, you are
past Part 1 here.

**Three things genuinely need a command line.** All three run in **Azure Cloud Shell** — the
`>_` icon in the blue bar at the top of the portal — so you never leave the browser. They are
called out where they occur and collected in [Appendix A](#appendix-a--the-command-line-bits).

**A note on click paths.** Azure renames blades every so often. When a path below does not match
what you see, the portal's **top search box** is the reliable way to navigate: type the resource
name or the service name and pick it from the results. The *concepts* below are stable even when
the labels move.

---

## What you will be doing

| Part | Where | Roughly |
|---|---|---|
| 1 | Azure portal | Resource group, Key Vault, two secrets, an app registration | 20 min |
| 2 | GitHub website | Paste four values into Settings | 5 min |
| 3 | GitHub website | Run the deploy workflow | 5 min |
| 4 | Azure portal | Let the job read the vault, then redeploy | 5 min |
| 5 | Azure portal + Cloud Shell | Smoke test | 5 min |

At the end you will have a Container Apps Job that runs quarterly and can be started by hand.

---

# Part 1 — Prerequisites, in the portal

## 1.1 Sign in and confirm the subscription

1. Go to <https://portal.azure.com> and sign in.
2. Top-right, click your account → **Switch directory** if you have more than one tenant, and
   pick the one holding the subscription you want to use.
3. In the top search box type **Subscriptions** and open it.
4. Note the **Subscription ID** of the one you will use — a GUID like
   `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. **Copy it somewhere; you need it in Part 2.**

## 1.2 Register the resource providers

A subscription that has never run Container Apps has the provider switched off, and the
deployment fails with `MissingSubscriptionRegistration` if you skip this.

1. Still in **Subscriptions**, click your subscription.
2. Left menu, under **Settings**, click **Resource providers**.
3. In the filter box type `Microsoft.App`.
4. Select the row **Microsoft.App**. If **Status** says *NotRegistered*, click **Register** in
   the toolbar.
5. Repeat for **Microsoft.OperationalInsights** and **Microsoft.KeyVault**.
6. First-time registration takes a few minutes. Click **Refresh** until all three read
   *Registered*. You can carry on with 1.3 while they finish.

## 1.3 Create the resource group

1. Top search box → **Resource groups** → open it.
2. Click **+ Create**.
3. **Subscription:** yours. **Resource group:** `rg-cust-cornerstone`. **Region:** `West US 2`.
   Container Apps is not available in every region; `West US 2` is, which is why it is the one
   used throughout. Everything else inherits this region, so pick it here and never again.
4. **Review + create** → **Create**.

## 1.4 Create the Key Vault

1. Top search box → **Key vaults** → **+ Create**.
2. **Basics** tab:
   - **Resource group:** `rg-cust-cornerstone`
   - **Key vault name:** `crr-kv-accounting`. Vault names are globally unique across all of
     Azure, so if you are rebuilding this from scratch and the name is taken, add a suffix and
     use your name everywhere this document says `crr-kv-accounting`.
   - **Region:** `West US 2`, same as the resource group.
   - **Pricing tier:** Standard.
   - **Days to retain deleted vaults:** leave the default. **Purge protection:** leave disabled
     unless your policy requires it — with it on, a vault of this name cannot be recreated for
     the retention period if you delete it.
3. **Access configuration** tab — **this one matters**:
   - **Permission model:** choose **Azure role-based access control (RBAC)**.
   - The older *Vault access policy* model also works, but every instruction below assumes RBAC,
     and RBAC is what the template expects.
4. **Networking** tab: leave public access enabled unless you have a policy against it.
5. **Review + create** → **Create**. Wait for *Your deployment is complete*, then
   **Go to resource**.

## 1.5 Give yourself permission to add secrets

With an RBAC vault, **being the subscription Owner is not enough to read or write secrets** —
the data plane has its own roles. This trips almost everyone once.

1. In your Key Vault, left menu → **Access control (IAM)**.
2. **+ Add** → **Add role assignment**.
3. **Role** tab: search for and select **Key Vault Secrets Officer** → **Next**.
4. **Members** tab: **Assign access to** = *User, group, or service principal* →
   **+ Select members** → search for yourself → select → **Select**.
5. **Review + assign** → **Review + assign**.
6. **Wait about a minute.** Role assignments take time to propagate; if the next step says
   *Forbidden*, that is what happened — wait and retry.

## 1.6 Add the two secrets

### 1.6a The Anthropic key

1. Key Vault left menu → **Objects** → **Secrets**.
2. **+ Generate/Import**.
3. **Upload options:** Manual.
   **Name:** `anthropic-api-key` — exactly this, lower-case, hyphens.
   **Secret value:** paste your key (starts `sk-ant-`). No quotes, no trailing space.
4. Leave activation/expiry blank. **Enabled:** Yes. → **Create**.

### 1.6b The Google service account — needs Cloud Shell

The vault needs the service-account JSON **base64-encoded onto a single line**, which is not
something the portal will do for you.

1. Click the **`>_`** Cloud Shell icon in the top blue bar. Choose **Bash** if asked. First run
   asks to create a storage account — accept.
2. Click the **Upload/Download files** icon in the Cloud Shell toolbar → **Upload** → choose
   your service-account `.json`.
3. Run, substituting your filename and vault name:

   ```bash
   base64 -w0 service-account.json > sa.b64
   az keyvault secret set \
     --vault-name crr-kv-accounting \
     --name google-service-account-b64 \
     --file sa.b64 \
     --output none
   echo "done"
   ```

4. Clean up the copies so they do not linger in your Cloud Shell storage:

   ```bash
   rm -f service-account.json sa.b64
   ```

5. Back in the portal, refresh **Secrets**. You should now see `anthropic-api-key` and
   `google-service-account-b64`.

> **Why not paste it in the portal?** You can, if you already have the base64 string —
> **Generate/Import** → name `google-service-account-b64` → paste. The Cloud Shell route exists
> because most people have the `.json` file, not its base64.

## 1.7 Create the app registration GitHub will sign in as

This is the portal equivalent of `az ad sp create-for-rbac`.

1. Top search box → **Microsoft Entra ID** (formerly Azure Active Directory).
2. Left menu → **App registrations** → **+ New registration**.
3. **Name:** `crr-github-actions`.
   **Supported account types:** *Accounts in this organizational directory only*.
   **Redirect URI:** leave blank.
4. **Register**.
5. On the app's **Overview** page, copy and keep:
   - **Application (client) ID**
   - **Directory (tenant) ID**

### Create its password

6. Left menu → **Certificates & secrets** → **Client secrets** tab → **+ New client secret**.
7. **Description:** `github-actions`. **Expires:** 12 or 24 months — put a calendar reminder,
   because deploys fail the day it expires.
8. **Add**.
9. **Copy the `Value` column now.** It is shown in full exactly once — the moment the page
   reloads after **Add**. Navigate away and it is masked forever.

> ### The single most common mistake in this whole document
>
> The **Client secrets** table has two columns that both look like the answer:
>
> | Column | What it is | Looks like |
> |---|---|---|
> | **Value** | ✅ the password — **this is what you want** | ~40 characters, mixed case, usually containing `~`, `.` or `-`, e.g. `Xy8Q~aB3...` |
> | **Secret ID** | ❌ an internal identifier, useless for signing in | a GUID: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
>
> Copying the Secret ID gets you this at the sign-in step, and nothing else in the run explains
> it:
>
> ```
> AADSTS7000215: Invalid client secret provided. Ensure the secret being sent in the
> request is the client secret value, not the client secret ID.
> ```
>
> **The check that catches it:** three of the four values in 1.9 *are* GUIDs, so a GUID in the
> `clientSecret` slot looks perfectly plausible. It is not. If your `clientSecret` matches the
> 8-4-4-4-12 hex shape, it is the Secret ID and the deploy will fail.
>
> **If you already navigated away and the Value is masked, it is gone** — it cannot be
> recovered. Delete that secret with the wastebasket icon, do steps 6–9 again, and copy the
> **Value** this time.

## 1.8 Give the app permission to deploy

### Contributor on the resource group

1. Top search box → **Resource groups** → `rg-cust-cornerstone`.
2. Left menu → **Access control (IAM)** → **+ Add** → **Add role assignment**.
3. **Role:** **Contributor** → **Next**.
4. **Members:** *User, group, or service principal* → **+ Select members** → search
   `crr-github-actions` → select → **Select**.
5. **Review + assign**.

### User Access Administrator on the Key Vault (optional but saves a step later)

The deploy workflow tries to grant the job's identity access to the vault. It can only do that
if it is allowed to hand out roles.

6. Go to your **Key Vault** → **Access control (IAM)** → **+ Add** → **Add role assignment**.
7. **Role:** **User Access Administrator** → **Next**.
8. **Members:** the same `crr-github-actions` app → **Review + assign**.

Skip this if your policy forbids it — Part 4 does the same thing by hand.

## 1.9 Assemble the credential JSON

GitHub needs these four values as one JSON blob. Build it in a text editor:

```json
{
  "clientId": "<Application (client) ID from 1.7>",
  "clientSecret": "<the Value from 1.7 step 9>",
  "subscriptionId": "<Subscription ID from 1.1>",
  "tenantId": "<Directory (tenant) ID from 1.7>"
}
```

Where each one comes from, and what a correct value looks like:

| Field | Where in the portal | Shape |
|---|---|---|
| `clientId` | 1.7 → app **Overview** → *Application (client) ID* | GUID |
| `clientSecret` | 1.7 → **Certificates & secrets** → the **Value** column | **not a GUID** — ~40 mixed characters |
| `subscriptionId` | 1.1 → **Subscriptions** | GUID |
| `tenantId` | 1.7 → app **Overview** → *Directory (tenant) ID* | GUID |

**Three GUIDs and one that is not.** If all four of your values are GUIDs, you have pasted the
Secret ID into `clientSecret` — go back to 1.7.

Keep the braces. Do not add trailing commas. Do not wrap the values in extra quotes or leave a
trailing newline inside one. Nothing else is needed — the longer JSON that the CLI prints
contains endpoint URLs that the login action fills in itself.

---

# Part 2 — GitHub, in the browser

Go to **<https://github.com/arcticbio/cornerstone.accounting.reports/settings/secrets/actions>**.

## 2.1 Secrets

**Secrets** tab → **New repository secret**, once per row:

| Name | Value |
|---|---|
| `AZURE_CREDENTIALS` | the whole JSON block from 1.9 |
| `ANTHROPIC_API_KEY` | your key — for the GitHub-hosted builds (see `SETUP-CREDENTIALS.md`) |
| `GOOGLE_SERVICE_ACCOUNT_B64` | the same base64 string as the vault secret |

## 2.2 Variables

**Variables** tab → **New repository variable**:

| Name | Value |
|---|---|
| `AZURE_RESOURCE_GROUP` | `rg-cust-cornerstone` |
| `AZURE_KEY_VAULT_NAME` | `crr-kv-accounting` |
| `CRR_GDRIVE_ROOT_FOLDER_ID` | `1_tUMelVG8trnjPmJWul0YXo23VgWgdSc` |

Variables, not Secrets — the workflow reads them as `vars.*`, and a resource group name you
cannot see when checking your work helps nobody.

## 2.3 Decide how Azure pulls the image

The image is at `ghcr.io/arcticbio/crr`. Packages from a private repository are private, and
**Azure cannot pull a private image without credentials.**

**Option A — make it public (simplest).** The image holds code, config and the golden labels
only; no tenant data ever enters it, and CI fails the build if `data/` appears inside.

1. <https://github.com/arcticbio?tab=packages> → the **crr** package
2. **Package settings** → scroll to **Danger Zone** → **Change visibility** → **Public**

**Option B — keep it private.**

1. <https://github.com/settings/tokens> → **Generate new token (classic)**
2. Tick **`read:packages`** and nothing else. Set an expiry.
3. Back in the repository's Actions **Secrets**, add `GHCR_PULL_USERNAME` (your GitHub username)
   and `GHCR_PULL_TOKEN` (the token). The workflow picks them up automatically.

---

# Part 3 — Deploy

You are deploying from GitHub's web UI rather than the portal, because that uses the template in
the repository — the one CI compiles on every push — instead of a copy that can drift.
[Appendix B](#appendix-b--deploying-from-the-portal-instead) covers deploying from the portal if
you would rather.

1. <https://github.com/arcticbio/cornerstone.accounting.reports/actions> → left sidebar →
   **Deploy to Azure**.
2. Blue banner → **Run workflow**.
3. Leave **Preview the changes without applying them** ticked. Leave everything else blank —
   blanks fall back to the variables you set in Part 2.
4. **Run workflow**, then click into the run and open the **az deployment group create** job.

**Read the What-if output.** Expect four `+ Create` lines: a Log Analytics workspace, a Container
Apps Environment, a Container Apps Job, and the job's identity. Nothing has changed yet.

If it fails here:

- *Missing repository variables* — the error names which; go back to 2.2.
- *`AADSTS7000215: Invalid client secret`* — the `clientSecret` in `AZURE_CREDENTIALS` is
  wrong, and nine times in ten it is the **Secret ID** pasted instead of the **Value**.
  See the boxed warning in 1.7. A secret past its expiry date gives `AADSTS7000222`.
- *Sign-in failure with no AADSTS code* — `AZURE_CREDENTIALS` is not valid JSON: a missing
  brace, a smart quote from a word processor, or a trailing comma.
- *AuthorizationFailed* — the Contributor assignment in 1.8 did not apply to `rg-cust-cornerstone`.

5. When the preview looks right, **Run workflow** again with **Preview** **unticked**.

The run deploys, then tries to grant the job's identity read access to the vault. If you skipped
the User Access Administrator assignment in 1.8, that step goes yellow and prints the command —
that is expected. Part 4 does it in the portal instead.

---

# Part 4 — Let the job read the vault

The job authenticates to Key Vault with a **managed identity that does not exist until the job
does** — which is why this cannot be part of the template.

1. Portal → your **Key Vault** → **Access control (IAM)** → **+ Add** → **Add role assignment**.
2. **Role:** **Key Vault Secrets User** → **Next**.
3. **Members:** change **Assign access to** to **Managed identity** → **+ Select members** →
   **Managed identity** dropdown → **Container Apps Job** → pick **crr-quarterly** → **Select**.
4. **Review + assign**.
5. Wait a minute, then go back to GitHub and **run the deploy workflow again** (Preview
   unticked) so the job picks up secrets it can now read.

---

# Part 5 — Smoke test

Two runs that touch neither Drive nor the model.

## 5.1 In the portal

1. Top search box → `crr-quarterly` → open the Container App Job.
2. **Overview** → **Run now** → confirm.
3. Left menu → **Execution history**. The execution should reach **Succeeded**.

**Run now** uses the arguments the job is configured with — a full build. For the two smoke
commands you need to override the arguments, and that needs Cloud Shell.

## 5.2 In Cloud Shell

Click **`>_`** in the top bar and run:

```bash
az containerapp job start --name crr-quarterly --resource-group rg-cust-cornerstone --args "version"
az containerapp job start --name crr-quarterly --resource-group rg-cust-cornerstone --args "validate-config"
```

Then watch:

```bash
az containerapp job execution list --name crr-quarterly --resource-group rg-cust-cornerstone --output table
```

`version` should print `crr 1.0.0`. `validate-config` should list 4 schemas, 3 output
definitions and 8 properties. If `version` works and `validate-config` does not, the image is
fine and the config copy is not — worth reporting as a bug.

## 5.3 Reading the result

**The runner's exit codes are 0 built, 2 needs review, 1 failed — and Azure marks any non-zero
exit as a Failed execution.** So an execution showing **Failed** is very often exit code 2,
meaning the packages built and one or more went to `review/` for a human. **Read the logs before
treating it as an incident.** The packages and manifests are in Drive either way.

---

# Part 6 — Logs

**Live:** Container App Job → **Monitoring** → **Log stream**.

**After the fact:** Container App Job → **Monitoring** → **Logs**, then run:

```kusto
ContainerAppConsoleLogs_CL
| where ContainerJobName_s == "crr-quarterly"
| order by TimeGenerated desc
| take 200
```

Every line is JSON. Page text, tenant names, file paths and secrets are never logged — only
document hashes, page counts and status. There is a test that fails the build if that stops
being true.

---

# Part 7 — Day to day, in the portal

**Rotate a key.** Key Vault → **Secrets** → the secret → **+ New Version** → paste the new value
→ **Create**. The job reads the current version on its next execution. Remember the GitHub
Actions copy is separate.

**Change the image.** Container App Job → **Containers** → **Edit and deploy** → change the
image tag → **Save**. Or re-run the deploy workflow with a different `image` input.

**Pause the schedule.** Re-run the deploy workflow with **Arm the quarterly cron** unticked —
that parks the cron on 31 February, which never arrives. Manual runs still work. Portal
alternative: Container App Job → **Job settings** → change the cron expression.

**Change when it runs.** The default `0 6 20 1,4,7,10 *` is 06:00 UTC on the 20th of January,
April, July and October — closing December, March, June and September. Edit `cronExpression` in
`infra/main.bicep` and redeploy, so the repository stays the source of truth.

**Delete everything.** Resource groups → `rg-cust-cornerstone` → **Delete resource group**. Nothing in Drive
or GitHub is touched.

---

# Appendix A — the command-line bits

Three things have no portal equivalent. All three run in **Cloud Shell** (`>_` in the top bar):

| What | Why | Where |
|---|---|---|
| Base64-encoding the service-account JSON | the portal will not encode a file for you | 1.6b |
| Starting the job with custom `--args` | **Run now** uses the configured arguments only | 5.2 |
| Granting a role when the portal IAM blade is restricted by policy | some tenants lock it down | equivalent commands in `SETUP-AZURE.md` |

Cloud Shell is a real Bash session in the browser with `az` already signed in as you. It has its
own storage — delete credential files after uploading them, as 1.6b step 4 does.

---

# Appendix B — deploying from the portal instead

Use this only if you cannot use the GitHub workflow. The portal's custom deployment takes **ARM
JSON**, not Bicep, so you need the compiled template.

1. <https://github.com/arcticbio/cornerstone.accounting.reports/actions> → the newest **CI** run
   on the build branch.
2. Scroll to **Artifacts** at the bottom of the run summary → download **arm-template** →
   unzip to get `main.json`.
3. Portal top search box → **Deploy a custom template**.
4. **Build your own template in the editor** → **Load file** → choose `main.json` → **Save**.
5. Fill the parameters:
   - **Resource group:** `rg-cust-cornerstone`
   - **Key Vault Name:** your vault
   - **Gdrive Root Folder Id:** `1_tUMelVG8trnjPmJWul0YXo23VgWgdSc`
   - **Image:** `ghcr.io/arcticbio/crr:build-v1`
   - leave the rest at their defaults
6. **Review + create** → **Create**.
7. Then do Part 4 and Part 5 as written.

The drawback is that this deploys whatever template you downloaded, not whatever is in the
repository — so if you take this path, note which CI run the artifact came from.

---

# Troubleshooting

| What you see | What it means | Fix |
|---|---|---|
| *MissingSubscriptionRegistration* | resource provider off | 1.2 |
| *Forbidden* when adding a secret | RBAC data-plane role not effective yet | 1.5, wait a minute, retry |
| The vault shows no Secrets blade content | you have management-plane but not data-plane access | 1.5 |
| Deploy: *AuthorizationFailed* | app is not Contributor on `rg-cust-cornerstone` | 1.8 |
| Deploy: *AADSTS7000215: Invalid client secret* | the **Secret ID** was pasted instead of the **Value** | 1.7 — delete the secret, make a new one, copy **Value** |
| Deploy: *AADSTS7000222* | the client secret has expired | 1.7 — new client secret, then update `AZURE_CREDENTIALS` |
| Deploy: *AADSTS700016* / app not found | wrong `clientId`, or wrong `tenantId` | 1.9 |
| Deploy: sign-in fails with no AADSTS code | `AZURE_CREDENTIALS` is not valid JSON | 1.9 |
| Job execution fails instantly, logs mention a secret | the job's identity cannot read the vault | Part 4, then redeploy |
| Job execution fails: *UNAUTHORIZED* / manifest unknown | private GHCR image, no pull credentials | 2.3 |
| Execution *Failed*, logs end with review reasons | **exit code 2 — packages need review** | normal; work the queue per `RUNBOOK.md` |
| Region missing from the Container Apps dropdown | Container Apps is not in that region | recreate the resource group in a supported one |
| `crr version` works, a real build fails at the classifier | vault's Anthropic key is wrong or expired | Part 7, rotate |
