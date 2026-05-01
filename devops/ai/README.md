# DWA AI Layer — DevOps

This folder contains operational scripts for provisioning and seeding the
Azure resources used by the DWA AI layer (Foundry, OpenAI deployments,
AI Search, App Insights).

## Scripts

| Script | Phase | Purpose |
|---|---|---|
| `00_provision.ps1` | 0 | Idempotently create / verify all Azure resources and assign RBAC |
| `01_create_search_indexes.py` | 2 | Create `dv-patterns` and `approved-decisions` indexes |
| `02_seed_dv_patterns.py` | 2 | Embed and upload seed Data Vault patterns |

## Prerequisites

- Azure CLI ≥ 2.60 (`az --version`)
- Logged in: `az login`
- Subscription set: `az account set --subscription <id>`
- The signed-in identity must have **Contributor** on the resource group
  and **User Access Administrator** (or **Owner**) to assign RBAC roles.

## First-time setup

```powershell
cd dwa
./devops/ai/00_provision.ps1
# When complete: copy emitted KEY=VALUE lines into .env
python -m dbt_builder.src.ai.hello_foundry   # smoke test
```

## Resource naming

| Resource | Name | Notes |
|---|---|---|
| Resource group | `rg-data-and-ai-chapter-database-refactoring` | Pre-existing |
| AI Foundry hub (AI Services account) | `dwa-foundry-hub` | Region: `westeurope` |
| Foundry project | `dwa-foundry-prj` | Child of hub |
| AI Search | `dwa-ai-search` | Tier: Standard S1 (vector + semantic) |
| App Insights | `dwa-ai-appi` | Connection-string-only auth |

> **GPT-5 availability**: as of May 2026, GPT-5 may not be available in
> `westeurope`. The provisioning script will report a clear error if a
> deployment fails; in that case re-run with `-Region swedencentral`
> for the failing model only (see script `--help`).
