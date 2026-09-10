# Azure Container Apps Job

The quarterly runner as a scheduled Container Apps Job (SPEC §14, D-13). GitHub Actions runs
the same image today; this is the target once Azure is provisioned.

**Setting this up for the first time?** Follow
[`../docs/SETUP-AZURE.md`](../docs/SETUP-AZURE.md) (CLI, starts with `./infra/bootstrap.sh`) or
[`../docs/SETUP-AZURE-PORTAL.md`](../docs/SETUP-AZURE-PORTAL.md) (Azure portal). Both cover the
parts this file assumes are already done. What follows is the reference for the template.

## What `main.bicep` deploys

| Resource | Why |
|---|---|
| Log Analytics workspace | where the job's stdout/stderr land, 90-day retention |
| Container Apps Environment | the compute the job runs in |
| Container Apps Job | schedule trigger (quarterly), 2 vCPU / 4 GiB, 3600 s timeout, 1 retry |

It does **not** create the Key Vault or the secrets. It references an existing vault, because a
secret in a template is a secret in source control and in every deployment log.

## One-command deploy

Prerequisites: an Azure subscription, a resource group, and a Key Vault holding two secrets.

```bash
az group create --name crr-rg --location westus2

az keyvault create --name crr-kv --resource-group crr-rg --location westus2 \
  --enable-rbac-authorization true

az keyvault secret set --vault-name crr-kv --name anthropic-api-key        --value "sk-ant-..."
az keyvault secret set --vault-name crr-kv --name google-service-account-b64 --value "$(base64 -w0 service-account.json)"

az deployment group create \
  --resource-group crr-rg \
  --template-file infra/main.bicep \
  --parameters \
      namePrefix=crr \
      keyVaultName=crr-kv \
      gdriveRootFolderId=1_tUMelVG8trnjPmJWul0YXo23VgWgdSc \
      image=ghcr.io/arcticbio/crr:build-v1
```

## After the first deploy: let the job read the vault

The job authenticates to Key Vault with a system-assigned identity, which does not exist until
the job does. Grant it read access once:

```bash
principal=$(az deployment group show -g crr-rg -n main --query properties.outputs.principalId.value -o tsv)
vault=$(az keyvault show -n crr-kv --query id -o tsv)

az role assignment create \
  --assignee-object-id "$principal" \
  --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" \
  --scope "$vault"
```

Re-run the deployment afterwards so the job picks up the secrets it can now read.

## Running it by hand

The schedule fires quarterly. To run one now:

```bash
# The period just ended — same thing the schedule does.
az containerapp job start --name crr-quarterly --resource-group crr-rg

# A specific period, or one property.
az containerapp job start --name crr-quarterly --resource-group crr-rg \
  --args "build --period 2026-09 --repo gdrive --classifier anthropic --property fort-grounds"

# A smoke test that needs neither Drive nor the bundle.
az containerapp job start --name crr-quarterly --resource-group crr-rg --args "version"
az containerapp job start --name crr-quarterly --resource-group crr-rg --args "validate-config"
```

Watch it:

```bash
az containerapp job execution list --name crr-quarterly --resource-group crr-rg -o table
az containerapp job logs show --name crr-quarterly --resource-group crr-rg --follow
```

## Exit codes

The job's execution status follows SPEC §6.8: **0** every property built, **2** at least one
package went to `review/`, **1** at least one property failed. Azure marks a non-zero exit as a
failed execution, so a review outcome shows up as a failed run — check the logs before treating
it as an incident. The packages and manifests are in Drive either way.

## Updating the image

The job pins a tag, not a digest. Pushing a new `:build-v1` is enough; the next execution pulls
it. To pin a release instead:

```bash
az deployment group create -g crr-rg --template-file infra/main.bicep \
  --parameters keyVaultName=crr-kv gdriveRootFolderId=<id> image=ghcr.io/arcticbio/crr:v1.0.0
```

## Turning the schedule off

```bash
az deployment group create -g crr-rg --template-file infra/main.bicep \
  --parameters keyVaultName=crr-kv gdriveRootFolderId=<id> scheduleEnabled=false
```

`scheduleEnabled=false` parks the cron on 31 February, which never comes. Manual starts still
work.
