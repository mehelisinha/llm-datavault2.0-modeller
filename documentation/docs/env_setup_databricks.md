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
