<#
.SYNOPSIS
    Idempotent provisioning of Azure resources for the DWA AI layer (Phase 0).

.DESCRIPTION
    Creates / verifies:
      - Azure AI Services account (kind=AIServices) — the "Foundry hub"
      - Azure AI Foundry project (child of the AI Services account)
      - Model deployments: gpt-4o, gpt-5, text-embedding-3-small
      - Azure AI Search (Standard S1)
      - Log Analytics workspace + Application Insights

    Uses API-key auth (no RBAC role assignments) so it works with
    Contributor-only permissions.

    Safe to re-run: every step is idempotent (checks for existence first).

.PARAMETER SubscriptionId
    Target Azure subscription. Defaults to the CMP - Open Engineering Sandbox.

.PARAMETER ResourceGroup
    Existing resource group to deploy into.

.PARAMETER Region
    Azure region for all resources.

.PARAMETER NameSuffix
    Optional suffix appended to globally-unique resource names
    (AI Services account, AI Search). Use this if default names collide.

.PARAMETER SearchSku
    AI Search tier: 'free' (€0, 50 MB / 3 indexes, no SLA, ONE per subscription),
    'basic' (~€68/mo, vector only), or 'standard' (~€245/mo, vector + semantic
    ranker). Default 'free' for thesis-scale workloads.

.EXAMPLE
    ./devops/ai/00_provision.ps1
    # Uses defaults (basic search); emits .env lines on success.

.EXAMPLE
    ./devops/ai/00_provision.ps1 -SearchSku standard
    # Provision S1 search (needed for semantic re-ranker in later phases).

.EXAMPLE
    ./devops/ai/00_provision.ps1 -NameSuffix "eon01"
    # Use if the default 'dwa-foundry-hub' / 'dwa-ai-search' names are taken.
#>

[CmdletBinding()]
param(
    [string]$SubscriptionId = "5e6b8f4d-257e-485d-957b-577be337833e",
    [string]$ResourceGroup  = "rg-data-and-ai-chapter-database-refactoring",
    [string]$Region         = "germanywestcentral",
    [string]$NameSuffix     = "",
    # AI Search SKU. Cost (germanywestcentral, May 2026):
    #   free     ≈ €0      — 50 MB / 3 indexes / ONE per subscription, no SLA
    #   basic    ≈ €68/mo  — vector search OK, NO semantic ranker
    #   standard ≈ €245/mo — vector + semantic ranker (S1)
    # Default 'free' for thesis-scale workloads (a few thousand columns ≈ <12 MB).
    # Override with -SearchSku basic / standard when production capacity is needed.
    [ValidateSet("free", "basic", "standard")]
    [string]$SearchSku      = "free"
)

$ErrorActionPreference = "Continue"
# Treat stderr from `az` as informational (it writes "ResourceNotFound" there
# during existence checks). We rely on $LASTEXITCODE explicitly.
$PSNativeCommandUseErrorActionPreference = $false

function Get-AzOrNull {
    <#
        Wrap an `az ... -o tsv` query that may legitimately return "not found".
        Returns the trimmed stdout on success, $null otherwise.
        Suppresses both stderr and any error records.
    #>
    $out = & $args[0] $args[1..($args.Count - 1)] 2>$null
    if ($LASTEXITCODE -eq 0 -and $out) { return ($out | Out-String).Trim() }
    return $null
}

# ── Resource names ────────────────────────────────────────────────────────────
$suffix         = if ($NameSuffix) { "-$NameSuffix" } else { "" }
$aiServicesName = "dwa-foundry-hub$suffix"
$projectName    = "dwa-foundry-prj"
$searchName     = "dwa-ai-search$suffix"
$lawName        = "dwa-ai-law"
$appiName       = "dwa-ai-appi"

# Model deployments: name, model, version, sku-name, sku-capacity
$deployments = @(
    @{ name = "gpt-4o";                 model = "gpt-4o";                 version = "2024-11-20"; sku = "GlobalStandard"; capacity = 30 },
    @{ name = "gpt-5";                  model = "gpt-5";                  version = "2025-08-07"; sku = "GlobalStandard"; capacity = 30 },
    @{ name = "text-embedding-3-small"; model = "text-embedding-3-small"; version = "1";          sku = "GlobalStandard"; capacity = 50 }
)

# ── Helpers ───────────────────────────────────────────────────────────────────
function Write-Step  { param([string]$m) Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Ok    { param([string]$m) Write-Host "    [ OK ] $m" -ForegroundColor Green }
function Write-Skip  { param([string]$m) Write-Host "    [SKIP] $m" -ForegroundColor DarkGray }
function Write-Warn2 { param([string]$m) Write-Host "    [WARN] $m" -ForegroundColor Yellow }
function Fail        { param([string]$m) Write-Host "    [FAIL] $m" -ForegroundColor Red; exit 1 }

function Invoke-Az {
    # Wrapper that surfaces stderr but doesn't auto-throw on non-zero
    # so callers can decide based on output. Returns stdout string.
    $out = & az @args 2>&1
    return ,$out
}

# ── 0. Pre-flight ─────────────────────────────────────────────────────────────
Write-Step "Pre-flight: Azure CLI"
$null = az --version 2>$null
if ($LASTEXITCODE -ne 0) { Fail "Azure CLI not on PATH. Open a new terminal and retry." }
Write-Ok "az CLI present"

az account set --subscription $SubscriptionId | Out-Null
$ctx = az account show -o json | ConvertFrom-Json
Write-Ok "Subscription: $($ctx.name)"
Write-Ok "User:         $($ctx.user.name)"

$null = az group show --name $ResourceGroup -o none 2>$null
if ($LASTEXITCODE -ne 0) { Fail "Resource group '$ResourceGroup' not found in subscription." }
Write-Ok "Resource group: $ResourceGroup ($Region)"

# Register required providers (idempotent)
Write-Step "Register resource providers"
foreach ($p in @("Microsoft.CognitiveServices", "Microsoft.Search", "Microsoft.Insights", "Microsoft.OperationalInsights")) {
    $state = az provider show --namespace $p --query registrationState -o tsv
    if ($state -ne "Registered") {
        az provider register --namespace $p --wait | Out-Null
        Write-Ok "$p registered"
    } else {
        Write-Skip "$p already registered"
    }
}

# ── 1. Log Analytics workspace ────────────────────────────────────────────────
Write-Step "Log Analytics workspace: $lawName"
$lawId = az monitor log-analytics workspace show -g $ResourceGroup -n $lawName --query id -o tsv 2>$null
if (-not $lawId) {
    az monitor log-analytics workspace create `
        -g $ResourceGroup -n $lawName -l $Region `
        --sku PerGB2018 -o none
    $lawId = az monitor log-analytics workspace show -g $ResourceGroup -n $lawName --query id -o tsv
    Write-Ok "Created"
} else {
    Write-Skip "Already exists"
}

# ── 2. Application Insights (optional — may fail behind corp proxy without ext) ──
Write-Step "Application Insights: $appiName (optional)"
$appiResId = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/microsoft.insights/components/$appiName"
$appiCs = $null
$existing = az resource show --ids $appiResId --query "properties.ConnectionString" -o tsv 2>$null
if ($LASTEXITCODE -eq 0 -and $existing) {
    $appiCs = $existing
    Write-Skip "Already exists"
} else {
    # Create via generic ARM (avoids needing the application-insights CLI extension)
    $appiProps = @{
        Application_Type    = "web"
        Flow_Type           = "Bluefield"
        Request_Source      = "rest"
        WorkspaceResourceId = $lawId
    } | ConvertTo-Json -Compress
    # Escape for CLI consumption
    $appiPropsArg = $appiProps -replace '"', '\"'
    az resource create `
        --resource-group $ResourceGroup `
        --name $appiName `
        --resource-type "microsoft.insights/components" `
        --location $Region `
        --kind web `
        --properties $appiPropsArg `
        --api-version "2020-02-02" `
        -o none 2>$null
    if ($LASTEXITCODE -eq 0) {
        $appiCs = az resource show --ids $appiResId --query "properties.ConnectionString" -o tsv 2>$null
        Write-Ok "Created"
    } else {
        Write-Warn2 "App Insights creation failed (corp proxy / permissions). Phase 0 smoke test does NOT require it; continuing."
    }
}

# ── 3. Azure AI Services account (Foundry hub) ────────────────────────────────
Write-Step "Azure AI Services account (Foundry hub): $aiServicesName"
$aisEndpoint = az cognitiveservices account show -g $ResourceGroup -n $aiServicesName --query "properties.endpoint" -o tsv 2>$null
if (-not $aisEndpoint) {
    az cognitiveservices account create `
        -g $ResourceGroup -n $aiServicesName -l $Region `
        --kind AIServices --sku S0 `
        --custom-domain $aiServicesName `
        --assign-identity `
        --yes -o none
    Write-Ok "Created"
} else {
    Write-Skip "Already exists"
}
$aisEndpoint    = az cognitiveservices account show -g $ResourceGroup -n $aiServicesName --query "properties.endpoint" -o tsv
$openaiEndpoint = "https://$aiServicesName.openai.azure.com/"
$aisKey         = az cognitiveservices account keys list -g $ResourceGroup -n $aiServicesName --query key1 -o tsv

# ── 4. Foundry project (child of AI Services account) ────────────────────────
Write-Step "Foundry project: $projectName"
$projectResId = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.CognitiveServices/accounts/$aiServicesName/projects/$projectName"
$existingProj = az resource show --ids $projectResId --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $existingProj) {
    az cognitiveservices account project create `
        -g $ResourceGroup --name $aiServicesName --project-name $projectName `
        -l $Region -o none 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Ok "Created" } else { Fail "Project creation failed" }
} else {
    Write-Skip "Already exists"
}
# Foundry project endpoint follows a deterministic format:
# https://<aiservices-name>.services.ai.azure.com/api/projects/<project-name>
$projEndpoint = "https://$aiServicesName.services.ai.azure.com/api/projects/$projectName"

# ── 5. Model deployments ──────────────────────────────────────────────────────
$failedDeployments = @()
foreach ($d in $deployments) {
    Write-Step "Model deployment: $($d.name) ($($d.model) v$($d.version))"
    $existing = az cognitiveservices account deployment show `
        -g $ResourceGroup -n $aiServicesName --deployment-name $d.name `
        --query name -o tsv 2>$null
    if ($existing) { Write-Skip "Already deployed"; continue }

    $output = az cognitiveservices account deployment create `
        -g $ResourceGroup -n $aiServicesName `
        --deployment-name $d.name `
        --model-name $d.model --model-version $d.version --model-format OpenAI `
        --sku-name $d.sku --sku-capacity $d.capacity `
        -o none 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Deployed (capacity $($d.capacity)K TPM, sku $($d.sku))"
    } else {
        Write-Warn2 "Deployment failed: $($d.model) v$($d.version) may not be available in $Region"
        Write-Warn2 "  $($output -join ' ')"
        $failedDeployments += $d.name
    }
}

# ── 6. Azure AI Search ($SearchSku tier) ─────────────────────────────────────
Write-Step "Azure AI Search: $searchName (sku=$SearchSku)"
$searchEndpoint = az search service show -g $ResourceGroup -n $searchName --query "hostingMode" -o tsv 2>$null
if (-not $searchEndpoint) {
    # The Free (F1) tier does not accept --partition-count / --replica-count;
    # paid tiers default to 1/1 anyway.
    if ($SearchSku -eq "free") {
        az search service create `
            -g $ResourceGroup -n $searchName -l $Region `
            --sku free -o none
    } else {
        az search service create `
            -g $ResourceGroup -n $searchName -l $Region `
            --sku $SearchSku --partition-count 1 --replica-count 1 -o none
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Created (sku=$SearchSku)"
    } else {
        Write-Warn2 "Search creation failed (sku=$SearchSku). If 'free' is exhausted in this subscription, retry with -SearchSku basic."
    }
} else {
    Write-Skip "Already exists"
}
$searchUrl = "https://$searchName.search.windows.net"
$searchKey = az search admin-key show -g $ResourceGroup --service-name $searchName --query primaryKey -o tsv

# ── 7. Emit .env lines ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  PROVISIONING COMPLETE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
if ($failedDeployments.Count -gt 0) {
    Write-Host ""
    Write-Warn2 "Failed deployments: $($failedDeployments -join ', ')"
    Write-Warn2 "Re-run with -Region swedencentral / eastus2 for those models,"
    Write-Warn2 "or remove them from `$deployments at the top of this script."
}

$envBlock = @"

# ── Generated by devops/ai/00_provision.ps1 on $(Get-Date -Format 'yyyy-MM-dd HH:mm') ──
DWA_AI_AZURE_SUBSCRIPTION_ID=$SubscriptionId
DWA_AI_AZURE_RESOURCE_GROUP=$ResourceGroup
DWA_AI_AZURE_REGION=$Region

DWA_AI_FOUNDRY_PROJECT_ENDPOINT=$projEndpoint

DWA_AI_AZURE_OPENAI_ENDPOINT=$openaiEndpoint
DWA_AI_AZURE_OPENAI_API_KEY=$aisKey
DWA_AI_AZURE_OPENAI_API_VERSION=2024-10-21

DWA_AI_CHAT_DEPLOYMENT_GPT4O=gpt-4o
DWA_AI_CHAT_DEPLOYMENT_GPT5=gpt-5
DWA_AI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

DWA_AI_SEARCH_ENDPOINT=$searchUrl
DWA_AI_SEARCH_ADMIN_KEY=$searchKey
DWA_AI_SEARCH_INDEX_PATTERNS=dv-patterns
DWA_AI_SEARCH_INDEX_DECISIONS=approved-decisions

DWA_AI_APPINSIGHTS_CONNECTION_STRING=$appiCs
"@

# Write to a sibling file so secrets are not echoed to terminal history
$envOutPath = Join-Path (Split-Path $PSScriptRoot -Parent) "..\\.env.generated"
$envOutPath = [System.IO.Path]::GetFullPath($envOutPath)
$envBlock | Set-Content -Path $envOutPath -Encoding UTF8 -NoNewline

Write-Host ""
Write-Host "Secrets written to:" -ForegroundColor Cyan
Write-Host "  $envOutPath" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Review the file:   notepad `"$envOutPath`""
Write-Host "  2. Move it to .env:   Move-Item -Force `"$envOutPath`" .env"
Write-Host "  3. Run smoke test:    python -m dbt_builder.src.ai.hello_foundry"
Write-Host ""
