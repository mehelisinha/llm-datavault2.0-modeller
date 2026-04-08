# Databricks notebook source
# COMMAND ----------

# MAGIC %run ./add_paths
# COMMAND ----------
from src.scripts.generate_dummy_data import create_datasets, datasets

# COMMAND ----------
catalog = "edh_unreg_silver_dev_st"
bronze_db = "bronze"
create_datasets(datasets, catalog, bronze_db)
