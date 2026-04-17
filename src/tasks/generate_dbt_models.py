# Databricks notebook source
# COMMAND ----------
# MAGIC %run ./add_paths

# COMMAND ----------
# ── Configuration ─────────────────────────────────────────────────────────────
# Adjust these values per system / environment.

SYSTEM_NAME   = "IEC61968_CIM"
METADATA_YAML = "poc/metadata/iec_cim_metadata.yaml"  # relative to dwa root
GITLAB_URL    = "https://git.example.com/repos/edh-group/dwa.git"
COMMIT_MSG    = f"Auto-generated dbt models for {SYSTEM_NAME}"

# COMMAND ----------
from pathlib import Path

from shared.logger.default_logger import default_logger
from shared.utils.proj_dir_mgr import ProjectDirBulder
from src.runners.dbt_builder import DBTBuilder
from src.runners.dbt_runner import DbtRunner

# `root_path` is injected into this notebook's scope by the %run ./add_paths cell above.
# add_paths.py walks up from the current notebook path until it finds the "src" directory,
# then sets root_path = that directory's parent (i.e. the dwa project root).
# In Databricks, %run executes the target notebook in the same variable scope, so all
# variables defined at module level in add_paths.py become available here.
#
# Example: if this notebook lives at /Users/me/DWA/dwa/src/tasks/generate_dbt_models
#          then root_path = Path('/Users/me/DWA/dwa')
#          and  dwa_root  = Path('/Workspace/Users/me/DWA/dwa')   (Databricks FUSE path)
dwa_root      = Path(f"/Workspace/{root_path}")
metadata_path = dwa_root / METADATA_YAML
output_path   = dwa_root.parent / "dbt" / SYSTEM_NAME

print(f"System     : {SYSTEM_NAME}")
print(f"Metadata   : {metadata_path}")
print(f"Output     : {output_path}")

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
# ── Generate dbt models ───────────────────────────────────────────────────────
builder = DBTBuilder(
    metadata_path=metadata_path,
    output_path=output_path,
)
builder.build()

# COMMAND ----------
# ── Push to GitLab ────────────────────────────────────────────────────────────
proj_dir.push_to_gitlab(commit_message=COMMIT_MSG)

# COMMAND ----------
# ── Run dbt pipeline ─────────────────────────────────────────────────────────
dbt = DbtRunner(project_path=output_path)
dbt.run_all_layers()

# COMMAND ----------
# ── Verify generated files ────────────────────────────────────────────────────
import os

print("\nGenerated files:")
for dirpath, _, filenames in os.walk(output_path):
    for fname in sorted(filenames):
        full = Path(dirpath) / fname
        print(f"  {full.relative_to(output_path)}")

