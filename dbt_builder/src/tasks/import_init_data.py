# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC POC Runner — end-to-end orchestration script for the DWA Data Vault POC.
# MAGIC
# MAGIC Runs the full pipeline on Databricks:
# MAGIC   1. Metadata-driven dbt model generation (SQL + YAML files)
# MAGIC   2. dbt run: bronze layer
# MAGIC   3. dbt run: staging layer
# MAGIC   4. dbt run: raw vault layer
# MAGIC   5. Validation: query Databricks to verify tables, row counts, and hash keys
# MAGIC
# MAGIC Prerequisites:
# MAGIC   - ~/.dbt/profiles.yml configured for iec_dv2_databricks profile
# MAGIC   - DATABRICKS_HOST and DATABRICKS_TOKEN env vars set (or in .envrc)
# MAGIC   - Python dependencies installed (uv pip install -e .)
# MAGIC
# MAGIC Usage:
# MAGIC     python poc_runner.py                    # full run
# MAGIC     python poc_runner.py --generate-only    # only regenerate dbt model files
# MAGIC     python poc_runner.py --skip-generate    # skip generation, run dbt directly
# MAGIC     python poc_runner.py --validate-only    # only run validation queries
# MAGIC     python poc_runner.py --profiles-dir /path/to/profiles  # custom profiles dir
# MAGIC

# COMMAND ----------

# MAGIC %run ./add_paths

# COMMAND ----------

# MAGIC %load_ext autoreload
# MAGIC %autoreload 2

# COMMAND ----------

from dbt_builder.src.scripts.generate_dummy_data import (
    DummyDataGenerator,
)
from dbt_builder.src.scripts.poc_runner_oop import Config, PocRunner

# COMMAND ----------

config = Config()
config.DEFAULT_METADATA_PATH

# COMMAND ----------


catalog = "edh_unreg_silver_dev_st"
bronze_db = "bronze"
# create_datasets(datasets, catalog, bronze_db)
# COMMAND ----------

# Append only the effective-satellite update events (no full bronze reload).
DummyDataGenerator(
    catalog=catalog, bronze_db=bronze_db
).insert_initial_data_all_tables()

# COMMAND ----------

# Append only the effective-satellite update events (no full bronze reload).
DummyDataGenerator(catalog=catalog, bronze_db=bronze_db).insert_eff_sat_updates(
    offset_minutes=300
)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * from edh_unreg_silver_dev_st.bronze.connectivity_nodes

# COMMAND ----------

poc_runner = PocRunner(
    catalog=catalog,
    raw_vault_schema="raw_vault",
    dbt_project_dir=config.DBT_PROJECT_DIR,
    models_output=config.DEFAULT_MODELS_OUTPUT,
    metadata_path=config.DEFAULT_METADATA_PATH,
)
poc_runner.run()

# COMMAND ----------

poc_runner.generator.generate()

# COMMAND ----------

# MAGIC %sql
# MAGIC select * from edh_unreg_silver_dev_st.bronze.hub_conducting_equipment
