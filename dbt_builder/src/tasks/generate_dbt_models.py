# Databricks notebook source
# COMMAND ----------
# MAGIC %run ./add_paths
# COMMAND ----------

# MAGIC %load_ext autoreload
# MAGIC %autoreload 2
# COMMAND ----------
# ── Configuration ─────────────────────────────────────────────────────────────
# Adjust these values per system / environment.

SYSTEM_NAME = "IEC61968_CIM"
METADATA_YAML = "poc/metadata/iec_cim_metadata.yaml"  # relative to dwa root — used as fallback

# Unity Catalog identifier for the system being built.  Must match
# ``system.catalog`` in the approved metadata YAML so the correct
# ADLS Gen2 path is resolved.
CATALOG_ID = "edh_unreg_silver_dev_st"

# ADLS Gen2 metadata store settings.
# Set METADATA_STORE_ACCOUNT to the storage account name (no suffix) to read
# the latest approved YAML from ADLS Gen2.  When left empty the notebook falls
# back to the local METADATA_YAML path (dev / legacy behaviour).
METADATA_STORE_ACCOUNT = ""  # e.g. "myaccount"
METADATA_STORE_CONTAINER = "dwa-metadata"
# Databricks secret scope + keys that hold the service-principal credentials.
# These are the same creds used by StorageSetupProvisioner.
SP_SECRET_SCOPE = "dwa-sp"
SP_CLIENT_ID_KEY = "client-id"
SP_CLIENT_SECRET_KEY = "client-secret"
SP_TENANT_ID_KEY = "tenant-id"

GITLAB_URL = "https://git.example.com/repos/edh-group/dwa.git"
COMMIT_MSG = f"Auto-generated dbt models for {SYSTEM_NAME}"

# COMMAND ----------
import os
from pathlib import Path

from pyspark import dbutils

from dbt_builder.src.runners.dbt_p_builder import DBTBuilder
from dbt_builder.src.runners.dbt_runner import DbtRunnerFactory
from shared.src.auth.token_mgr import TokenManager
from shared.src.logger.default_logger import default_logger
from shared.utils.proj_dir_mgr import ProjectDirBulder

# `root_path` is injected into this notebook's scope by the %run ./add_paths cell above.
# add_paths.py walks up from the current notebook path until it finds the "src" directory,
# then sets root_path = that directory's parent (i.e. the dwa project root).
# In Databricks, %run executes the target notebook in the same variable scope, so all
# variables defined at module level in add_paths.py become available here.
#
# Example: if this notebook lives at /Users/me/DWA/dwa/src/tasks/generate_dbt_models
#          then root_path = Path('/Users/me/DWA/dwa')
#          and  dwa_root  = Path('/Workspace/Users/me/DWA/dwa')   (Databricks FUSE path)
dwa_root = Path(f"/Workspace/{root_path}")
output_path = dwa_root.parent / "dbt" / SYSTEM_NAME

print(f"System     : {SYSTEM_NAME}")
print(f"Output     : {output_path}")

# ── Resolve metadata path ─────────────────────────────────────────────────────
# When METADATA_STORE_ACCOUNT is configured we download the latest approved
# YAML from ADLS Gen2; otherwise we fall back to the local file (dev/legacy).
if METADATA_STORE_ACCOUNT:
    from dbt_builder.src.utils.yaml_store import AdlsYamlStore

    _tenant_id = dbutils.secrets.get(scope=SP_SECRET_SCOPE, key=SP_TENANT_ID_KEY)
    _client_id = dbutils.secrets.get(scope=SP_SECRET_SCOPE, key=SP_CLIENT_ID_KEY)
    _client_sec = dbutils.secrets.get(scope=SP_SECRET_SCOPE, key=SP_CLIENT_SECRET_KEY)

    _yaml_store = AdlsYamlStore(
        account_name=METADATA_STORE_ACCOUNT,
        container=METADATA_STORE_CONTAINER,
        tenant_id=_tenant_id,
        client_id=_client_id,
        client_secret=_client_sec,
    )
    _yaml_content = _yaml_store.get_latest(CATALOG_ID)
    metadata_path = Path(f"/tmp/metadata_{CATALOG_ID}.yaml")
    metadata_path.write_text(_yaml_content, encoding="utf-8")
    print(
        f"Metadata   : ADLS Gen2 → catalogs/{CATALOG_ID}/latest.yaml  (cached at {metadata_path})"
    )
else:
    metadata_path = dwa_root.parent / METADATA_YAML
    print(f"Metadata   : {metadata_path}  (local fallback)")

# COMMAND ----------
# ── Prepare output directory & git remote ────────────────────────────────────
proj_dir = ProjectDirBulder(
    system=SYSTEM_NAME,
    gitlab_url=GITLAB_URL,
    logger=default_logger,
)
# Override the computed target_path with our dbt/{system} directory so we
# avoid the Path.parts bug in ProjectDirBulder and keep the correct layout.
proj_dir._target_path = str(output_path)
proj_dir.create_and_clone_git()

# COMMAND ----------
# ── Set Env Token ───────────────────────────────────────────────────────
token_mgr = TokenManager(default_logger)
os.environ["DBT_DATABRICKS_TOKEN"] = token_mgr.api_token

host = spark.conf.get("spark.databricks.workspaceUrl")
http = "https://" + host
org_id = spark.conf.get("spark.databricks.clusterUsageTags.orgId")
cluster_id = spark.conf.get("spark.databricks.clusterUsageTags.clusterId")
http_path = f"/sql/protocolv1/o/{org_id}/{cluster_id}"

print(f"host:      {http}")
print(f"http_path: {http_path}")

os.environ["DBT_DATABRICKS_HTTP_PATH"] = http_path
os.environ["DBT_DATABRICKS_HOST"] = "https://" + host
# COMMAND ----------
# ── Generate dbt models ───────────────────────────────────────────────────────
builder = DBTBuilder(
    metadata_path=metadata_path,
    output_path=output_path,
)
builder.build()

# COMMAND ----------
# ── Push to GitLab ────────────────────────────────────────────────────────────
# proj_dir.push_to_gitlab(commit_message=COMMIT_MSG)

# COMMAND ----------
# ── Run dbt pipeline ─────────────────────────────────────────────────────────
dbt = DbtRunnerFactory.create(
    project_path=output_path,
    profiles_dir=output_path,
    logger=default_logger,
    runner_type="dbt",
)
# COMMAND ----------
dbt.deps()
# COMMAND ----------
dbt.run_layer(tag="staging")

# COMMAND ----------
dbt.run_layer(tag="raw_vault")
# COMMAND ----------
dbutils.notebook.exit(
    "DBT model generation complete. Check the output directory and GitLab repository for results."
)
# COMMAND ----------
# ── Verify generated files ────────────────────────────────────────────────────
import os

print("\nGenerated files:")
for dirpath, _, filenames in os.walk(output_path):
    for fname in sorted(filenames):
        full = Path(dirpath) / fname
        print(f"  {full.relative_to(output_path)}")
