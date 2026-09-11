#!/usr/bin/env bash
#
# One-time Azure bootstrap for the Cornerstone Report Runner (docs/SETUP-AZURE.md).
#
# Creates: a resource group, a Key Vault, the two secrets, and a service principal for GitHub
# Actions. Everything after this is done by the `Deploy to Azure` workflow.
#
# Idempotent: re-running it will not duplicate anything, but it WILL print a fresh service
# principal password if you let it recreate the credential. Read the prompts.
#
#   ./infra/bootstrap.sh
#
set -euo pipefail

# ---------------------------------------------------------------- settings you may change ---
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-cust-cornerstone}"
LOCATION="${LOCATION:-westus2}"
KEY_VAULT_NAME="${KEY_VAULT_NAME:-crr-kv-accounting}"   # globally unique; reused if it already exists
SP_NAME="${SP_NAME:-crr-github-actions}"
# ---------------------------------------------------------------------------------------------

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
need() { command -v "$1" >/dev/null || { echo "missing required tool: $1"; exit 1; }; }

need az
az account show >/dev/null 2>&1 || { echo "Run 'az login' first."; exit 1; }

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
say "Subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"
read -r -p "Deploy into this subscription? [y/N] " ok
[ "$ok" = "y" ] || { echo "Switch with: az account set --subscription <name-or-id>"; exit 1; }

if [ -z "$KEY_VAULT_NAME" ]; then
  KEY_VAULT_NAME="crr-kv-$(tr -dc 'a-z0-9' </dev/urandom | head -c 6)"
fi

say "Registering resource providers (safe to re-run; can take a few minutes the first time)"
for provider in Microsoft.App Microsoft.OperationalInsights Microsoft.KeyVault; do
  state=$(az provider show -n "$provider" --query registrationState -o tsv 2>/dev/null || echo NotRegistered)
  if [ "$state" != "Registered" ]; then
    echo "  registering $provider ..."
    az provider register -n "$provider" --wait
  fi
  echo "  $provider: $(az provider show -n "$provider" --query registrationState -o tsv)"
done

say "Resource group: $RESOURCE_GROUP ($LOCATION)"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
echo "  ok"

say "Key Vault: $KEY_VAULT_NAME"
if az keyvault show --name "$KEY_VAULT_NAME" >/dev/null 2>&1; then
  echo "  already exists, reusing"
else
  az keyvault create \
    --name "$KEY_VAULT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --enable-rbac-authorization true \
    --output none
  echo "  created"
fi

# You need to be able to write secrets into the vault you just made. With RBAC vaults, being
# the subscription Owner is not enough on its own — the data plane needs its own role.
say "Granting yourself 'Key Vault Secrets Officer' on the vault"
MY_ID=$(az ad signed-in-user show --query id -o tsv)
VAULT_ID=$(az keyvault show --name "$KEY_VAULT_NAME" --query id -o tsv)
az role assignment create \
  --assignee-object-id "$MY_ID" --assignee-principal-type User \
  --role "Key Vault Secrets Officer" --scope "$VAULT_ID" --output none 2>/dev/null \
  && echo "  granted" || echo "  already granted (or you lack permission — see step 3 of the doc)"
echo "  waiting 30s for the role assignment to take effect"
sleep 30

say "Secrets"
read -r -s -p "  Anthropic API key (sk-ant-...): " ANTHROPIC_KEY; echo
[ -n "$ANTHROPIC_KEY" ] || { echo "  empty; aborting"; exit 1; }
az keyvault secret set --vault-name "$KEY_VAULT_NAME" \
  --name anthropic-api-key --value "$ANTHROPIC_KEY" --output none
echo "  anthropic-api-key: set"

read -r -p "  Path to the Google service-account JSON: " GOOGLE_JSON
[ -f "$GOOGLE_JSON" ] || { echo "  no such file; aborting"; exit 1; }
if base64 --help 2>&1 | grep -q -- '-w'; then
  GOOGLE_B64=$(base64 -w0 "$GOOGLE_JSON")      # GNU
else
  GOOGLE_B64=$(base64 -i "$GOOGLE_JSON" | tr -d '\n')   # BSD/macOS
fi
az keyvault secret set --vault-name "$KEY_VAULT_NAME" \
  --name google-service-account-b64 --value "$GOOGLE_B64" --output none
echo "  google-service-account-b64: set"

say "Service principal for GitHub Actions: $SP_NAME"
echo "  Contributor on the resource group, plus User Access Administrator on the vault so the"
echo "  deploy workflow can grant the job's identity read access to the secrets."
SP_JSON=$(az ad sp create-for-rbac \
  --name "$SP_NAME" \
  --role Contributor \
  --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" \
  --json-auth)
SP_APP_ID=$(echo "$SP_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin)["clientId"])')
if az role assignment create \
     --assignee "$SP_APP_ID" \
     --role "User Access Administrator" \
     --scope "$VAULT_ID" --output none 2>/dev/null; then
  echo "  granted User Access Administrator on the vault"
else
  echo "  could not grant User Access Administrator (needs Owner on the vault)."
  echo "  Not fatal: the deploy workflow will print the one command to run by hand."
fi

cat <<EOF

================================================================================
 Put these into GitHub: Settings → Secrets and variables → Actions
================================================================================

 SECRETS tab
 -----------
 AZURE_CREDENTIALS   (paste the whole JSON block below, braces included)

$SP_JSON

 VARIABLES tab
 -------------
 AZURE_RESOURCE_GROUP    $RESOURCE_GROUP
 AZURE_KEY_VAULT_NAME    $KEY_VAULT_NAME

 Then: Actions → "Deploy to Azure" → Run workflow (leave "Preview" ticked first).
 Full walkthrough: docs/SETUP-AZURE.md
================================================================================

EOF
