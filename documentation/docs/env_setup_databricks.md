# Databricks dbt Profile Setup

This guide shows how to configure your local `~/.dbt/profiles.yml` to connect dbt to the Databricks workspace used in this project.

## Prerequisites

- Access to the Databricks workspace (URL from `databricks.yml`)
- A personal access token (PAT) from Databricks
- A SQL Warehouse or All-Purpose Cluster HTTP path

---

## 1. Get Your Databricks Credentials

### Workspace URL
From `databricks.yml`:
```
https://redacted-host.example.net    ← local_dev_unreg
https://redacted-host.example.net    ← local_dev_reg
```

### Personal Access Token (PAT)
1. Open the Databricks workspace in your browser
2. Click your username (top right) → **Settings** → **Developer** → **Access Tokens**
3. Click **Generate New Token**, add a description, set an expiry
4. Copy the token value (you won't see it again)

### HTTP Path (SQL Warehouse or Cluster)
**SQL Warehouse** (recommended for dbt):
1. In Databricks → **SQL** → **SQL Warehouses**
2. Click your warehouse → **Connection Details** tab
3. Copy the **HTTP path** (format: `/sql/1.0/warehouses/<id>`)

**All-Purpose Cluster**:
1. In Databricks → **Compute** → click your cluster → **Advanced Options** → **JDBC/ODBC**
2. Copy the **JDBC URL** path (format: `/sql/protocolv1/o/<org_id>/<cluster_id>`)

---

## 2. Set Environment Variables

Add to your `.envrc` (already gitignored):

```bash
export DATABRICKS_HOST="https://redacted-host.example.net"
export DATABRICKS_TOKEN="dapi..."
export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/<your_warehouse_id>"
```

Then activate:
```bash
source .envrc
# or if using direnv:
direnv allow
```

---

## 3. Create `~/.dbt/profiles.yml`

Create or edit `~/.dbt/profiles.yml` with the following content:

```yaml
iec_dv2_databricks:
  target: dev
  outputs:
    dev:
      type: databricks
      host: "{{ env_var('DATABRICKS_HOST') | replace('https://', '') }}"
      http_path: "{{ env_var('DATABRICKS_HTTP_PATH') }}"
      token: "{{ env_var('DATABRICKS_TOKEN') }}"
      catalog: edh_unreg_silver_dev_st    # Unity Catalog name
      schema: raw_vault                   # default schema
      threads: 4
```

> **Note**: The profile name `iec_dv2_databricks` must match the `profile:` field in `src/dbt_project.yml`.

---

## 4. Test the Connection

```bash
cd src/
dbt debug --profiles-dir ~/.dbt --project-dir .
```

Expected output:
```
All checks passed!
```

---

## 5. Run the POC

### Option A — Full end-to-end run
```bash
cd <project_root>
python src/scripts/poc_runner.py
```

### Option B — Step by step
```bash
# 1. Generate dbt models from metadata
python src/scripts/generate_models.py --output models/

# 2. Preview generated SQL without writing (dry run)
python src/scripts/generate_models.py --dry-run

# 3. Run dbt layers
cd src/
dbt run --select tag:bronze --profiles-dir ~/.dbt
dbt run --select tag:staging --profiles-dir ~/.dbt
dbt run --select tag:raw_vault --profiles-dir ~/.dbt

# 4. Run data quality tests
dbt test --profiles-dir ~/.dbt

# 5. Validate on Databricks
DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/..." python src/scripts/poc_runner.py --validate-only
```

---

## 5b. (Optional) Drive the UI Catalog Dropdown from Live Unity Catalog

The discovery API has three modes, set via `DWA_API_DISCOVERY_MODE`:

| Mode         | What it does                                                              | When to use |
| ------------ | ------------------------------------------------------------------------- | ----------- |
| `stub`       | Reads catalogs/schemas/tables from `poc/metadata/*.yaml`. Default.        | Offline dev, CI, no Databricks login required. |
| `spark`      | Runs `SHOW CATALOGS / SCHEMAS / TABLES` through `get_spark()`.            | When you already have Databricks Connect attached to a cluster and want the same compute path as dbt. |
| `databricks` | Calls the Unity Catalog REST API via `databricks-sdk`. No cluster needed. | Local dev when you just want the UI to reflect every catalog your identity can see, with sub-second responses. |

### Switching the local API to `databricks` mode

1. Make sure `databricks-sdk` is importable (it ships with `databricks-connect`, already pinned in `pyproject.toml`).
2. Sign in once with the Azure CLI:
   ```bash
   az login
   az account set --subscription 5e6b8f4d-257e-485d-957b-577be337833e
   ```
3. Append these to `dwa/.env` (already gitignored):
   ```bash
   DWA_API_DISCOVERY_MODE=databricks
   DWA_API_DATABRICKS_HOST=https://redacted-host.example.net
   DWA_API_DATABRICKS_AUTH_TYPE=azure-cli
   # Leave DWA_API_DATABRICKS_TOKEN blank — Azure CLI OAuth does not need one.
   ```
4. Restart the dev API (`pnpm dev` from `dwa/`). Hit `/api/discovery/catalogs` —
   the response now lists every catalog your Databricks identity has
   `USE CATALOG` on, not just the two stubbed YAMLs.

### Falling back to PAT auth

If your environment cannot use `az login` (e.g. headless CI), use a PAT instead:

```bash
DWA_API_DISCOVERY_MODE=databricks
DWA_API_DATABRICKS_HOST=https://redacted-host.example.net
DWA_API_DATABRICKS_TOKEN=dapi...
# DWA_API_DATABRICKS_AUTH_TYPE optional — SDK detects PAT from token presence.
```

### Behavior of `/api/discovery/snapshot` in `databricks` mode

Snapshot uses `WorkspaceClient.tables.get(full_name=...)` for each table that
passes the include/exclude filter. That means snapshot cost is proportional to
the **filtered** table count, not the full schema. For very large catalogs we
recommend always providing `include_patterns` or an explicit `tables` allowlist
in the snapshot request body.

### Greenfield builds: `vault_schema` is optional

For a first-time Data Vault build there is no existing `hub_*` / `lnk_*` /
`sat_*` schema to diff against. In that case **omit `vault_schema`** from the
request body (or leave the dropdown blank in the UI). The backend then emits
an empty `CatalogSnapshot` and the diff analyzer categorises every bronze
table as `NEW` — the correct semantics for a greenfield run.

Sending `vault_schema: ""` is explicitly rejected with HTTP 422 (the schema
field is `min_length=1` when present). Use `null` / omit the field instead.

The "Generate Vault" pipeline button still requires `vault_schema` because the
generator needs to know where to materialise the new hubs/links/sats.

---

## 6. Expected Results

After a successful run, the following Delta tables should exist in:
`edh_unreg_silver_dev_st.raw_vault`

| Table | Description | Expected Rows |
|---|---|---|
| `hub_conducting_equipment` | CE business keys | 5 (4 unique equipment) |
| `hub_connectivity_node` | CN business keys | 4 |
| `hub_terminal` | Terminal business keys | 9 |
| `lnk_terminal_equipment_node` | Terminal–CE–CN relationships | 9+ |
| `sat_conducting_equipment_details` | Static CE attributes | 5+ |
| `sat_conducting_equipment_operational` | CE status history | 6+ (includes SWAP scenario) |
| `sat_connectivity_node_details` | CN descriptive history | 6 (includes maintenance update) |
| `sat_terminal_details` | Terminal attribute history | 11+ |
| `eff_sat_terminal_equipment_node` | Terminal lifecycle (CDC) | 11+ |

### Hash Key Verification
- MD5: 32-character hex string
- SHA256: 64-character hex string
- All HK columns should be non-null for valid records

### SWAP Scenario Validation
`CE-SW-001` (Switch_Alpha_Feeder7) should have ≥ 2 rows in `sat_conducting_equipment_operational`:
- Row 1: `asset_status = 'InService'` at t+0
- Row 2: `asset_status = 'OutOfService'` at t+90min
- Row 3: `asset_status = 'Retired'` at t+150min (DELETE → satellite end)
