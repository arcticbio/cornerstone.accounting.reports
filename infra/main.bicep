// Cornerstone Report Runner — Azure Container Apps Job (SPEC §14, D-13).
//
// Resource-group scoped. Deploys Log Analytics, a Container Apps Environment and a scheduled
// Container Apps Job that runs the GHCR image quarterly and can also be started by hand.
//
// Secrets are *referenced* from an existing Key Vault, never created here: a secret in a
// template is a secret in source control and in every deployment log.

targetScope = 'resourceGroup'

@description('Prefix for every resource name. Keep it short — some Azure names cap at 32 chars.')
@minLength(3)
@maxLength(16)
param namePrefix string = 'crr'

@description('Location for all resources. Defaults to the resource group\'s location.')
param location string = resourceGroup().location

@description('Container image to run, including tag.')
param image string = 'ghcr.io/arcticbio/crr:build-v1'

@description('Name of an existing Key Vault holding the two secrets. Must be in this subscription.')
param keyVaultName string

@description('Key Vault secret name holding the Anthropic API key.')
param anthropicSecretName string = 'anthropic-api-key'

@description('Key Vault secret name holding the base64 service-account JSON.')
param googleSecretName string = 'google-service-account-b64'

@description('Drive folder id that holds the property-manager folders. Not a secret.')
param gdriveRootFolderId string

@description('Quarterly schedule, UTC. Default: 06:00 on the 20th of Jan, Apr, Jul, Oct.')
param cronExpression string = '0 6 20 1,4,7,10 *'

@description('Set false to deploy the job without arming the schedule.')
param scheduleEnabled bool = true

@description('GHCR is public for this image; set a username/token to pull a private one.')
param registryUsername string = ''

@secure()
@description('GHCR token. Leave empty for an anonymous pull of a public image.')
param registryPassword string = ''

var logAnalyticsName = '${namePrefix}-logs'
var environmentName = '${namePrefix}-env'
var jobName = '${namePrefix}-quarterly'
var usesPrivateRegistry = !empty(registryUsername)

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 90
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// A system-assigned identity is what reads Key Vault; grant it `Key Vault Secrets User` on the
// vault after the first deploy (infra/README.md says how).
resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: jobName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: environment.id
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 3600
      replicaRetryLimit: 1
      scheduleTriggerConfig: {
        cronExpression: scheduleEnabled ? cronExpression : '0 0 31 2 *' // 31 February: never
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: usesPrivateRegistry ? [
        {
          server: 'ghcr.io'
          username: registryUsername
          passwordSecretRef: 'registry-password'
        }
      ] : []
      secrets: concat([
        {
          name: 'anthropic-api-key'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/${anthropicSecretName}'
          identity: 'system'
        }
        {
          name: 'google-service-account-b64'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/${googleSecretName}'
          identity: 'system'
        }
      ], usesPrivateRegistry ? [
        {
          name: 'registry-password'
          value: registryPassword
        }
      ] : [])
    }
    template: {
      containers: [
        {
          name: 'crr'
          image: image
          // No --period: the runner defaults to the month just ended, which is exactly the
          // period a quarterly run on the 20th is closing. Start the job by hand with
          // `--args` to rebuild any other period (infra/README.md).
          args: [
            'build'
            '--repo'
            'gdrive'
            '--classifier'
            'anthropic'
          ]
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
            {
              name: 'ANTHROPIC_API_KEY'
              secretRef: 'anthropic-api-key'
            }
            {
              name: 'GOOGLE_SERVICE_ACCOUNT_B64'
              secretRef: 'google-service-account-b64'
            }
            {
              name: 'CRR_GDRIVE_ROOT_FOLDER_ID'
              value: gdriveRootFolderId
            }
            {
              name: 'CRR_REPO'
              value: 'gdrive'
            }
            {
              name: 'CRR_WORK_DIR'
              value: '/work'
            }
          ]
        }
      ]
    }
  }
}

output jobName string = job.name
output environmentId string = environment.id
output principalId string = job.identity.principalId
output logAnalyticsWorkspaceId string = logAnalytics.id
