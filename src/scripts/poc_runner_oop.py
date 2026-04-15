#!/usr/bin/env python3
"""
OOP-based POC Runner — end-to-end orchestration for DWA Data Vault POC.

Key changes:
- Clean OOP structure
- Programmatic dbt invocation (dbtRunner)
- No Databricks host/token usage (runs inside Databricks)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
from typing import ClassVar

from dbt.cli.main import dbtRunner, dbtRunnerResult

from shared.logger.default_logger import default_logger
from src.scripts.generate_models import MetadataModelGenerator
from src.utils.spark import spark


@dataclass
class Config:
    PROJECT_ROOT: ClassVar[Path] = Path.cwd().parent.parent
    SRC_DIR: ClassVar[Path] = PROJECT_ROOT / "src"

    DEFAULT_METADATA_PATH: ClassVar[Path] = SRC_DIR / "metadata" / "iec_cim_metadata.yaml"
    DBT_PROJECT_DIR: ClassVar[Path] = SRC_DIR
    DEFAULT_MODELS_OUTPUT: ClassVar[Path] = PROJECT_ROOT / "models"

    CATALOG: ClassVar[str] = "edh_unreg_silver_dev_st"
    RAW_VAULT_SCHEMA: ClassVar[str] = "raw_vault"


# sys.path.insert(0, str(Config.SRC_DIR))


# ---------------------------------------------------------------------------
# dbt Runner
# ---------------------------------------------------------------------------


class DbtService:
    def __init__(self, dbt_project_dir: Path = Config.DBT_PROJECT_DIR):
        self.dbt = dbtRunner()
        self.dbt_project_dir = dbt_project_dir

    def run(self, select: str) -> None:
        default_logger.info(f"Running dbt for {select}")

        cli_args = [
            "run",
            "--select",
            select,
            "--project-dir",
            str(self.dbt_project_dir),
        ]

        result: dbtRunnerResult = self.dbt.invoke(cli_args)

        if result.success:
            default_logger.info(f"dbt run succeeded for {select}")
        else:
            default_logger.info(f"dbt run failed for {select}")
            raise RuntimeError(f"dbt run failed for {select}")

        for r in result.result:
            default_logger.info(f"  {r.node.name}: {r.status}")


# ---------------------------------------------------------------------------
# Model Generator
# ---------------------------------------------------------------------------


class ModelGenerator:
    def __init__(self, metadata_path: Path, output: Path, overwrite: bool = True):
        self.metadata = metadata_path
        self.output = output
        self.overwrite = overwrite

    def generate(self) -> None:
        default_logger.info("Generating dbt models from metadata")

        generator = MetadataModelGenerator(
            config_path=self.metadata,
            output_path=self.output,
            overwrite=self.overwrite,
        )
        # project_yml_generator = DBTProject(name ='iec_dv2', version='1.0.0')

        generator.run()
        # project_yml_generator.generate()

        default_logger.info("Model generation completed")

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class Validator:
    TABLES = [
        "hub_conducting_equipment",
        "hub_connectivity_node",
        "hub_terminal",
        "lnk_terminal_equipment_node",
        "sat_conducting_equipment_details",
        "sat_conducting_equipment_operational",
        "sat_connectivity_node_details",
        "sat_terminal_details",
        "eff_sat_terminal_equipment_node",
    ]

    def __init__(self, catalog:str, raw_vault_schema:str):
        self.catalog = catalog
        self.raw_vault_schema = raw_vault_schema

    def validate(self) -> None:
        default_logger.info("Validating tables")

        all_ok = True

        for table in self.TABLES:
            full_table = (
                f"{self.catalog}.{self.raw_vault_schema}.{table}"
            )

            try:
                count = spark.sql(
                    f"SELECT COUNT(*) as cnt FROM {full_table}"
                ).collect()[0][0]

                status = "OK" if count > 0 else "WARN"
                default_logger.info(f"  {full_table}: {count} rows, status: {status}")

                if count == 0:
                    all_ok = False

            except Exception as e:
                default_logger.info(f"  {full_table}: ERROR — {e}")
                all_ok = False

        self._validate_hash_key()
        self._validate_swap()

        if all_ok:
            default_logger.info("All validation checks passed")
        else:
            default_logger.info("Validation completed with warnings")

    def _validate_hash_key(self) -> None:
        default_logger.info("Checking HK format")

        df = spark.sql(
            f"""
            SELECT HK_CONDUCTING_EQUIPMENT
            FROM {self.catalog}.{self.raw_vault_schema}.hub_conducting_equipment
            LIMIT 3
            """
        )

        for row in df.collect():
            hk = row[0]

            if hk and len(hk) == 32:
                default_logger.info(f"  HK (MD5): {hk} - OK")
            elif hk and len(hk) == 64:
                default_logger.info(f"  HK (SHA256): {hk} - OK")
            else:
                default_logger.info(f"  Unexpected HK length: {hk} - WARN")

    def _validate_swap(self) -> None:
        default_logger.info("Checking SWAP scenario")

        query = f"""
        SELECT COUNT(*) as cnt
        FROM {self.catalog}.{self.raw_vault_schema}.sat_conducting_equipment_operational s
        JOIN {self.catalog}.{self.raw_vault_schema}.hub_conducting_equipment h
          ON s.HK_CONDUCTING_EQUIPMENT = h.HK_CONDUCTING_EQUIPMENT
        WHERE h.mrid = 'CE-SW-001'
        """

        count = spark.sql(query).collect()[0][0]

        if count >= 2:
            default_logger.info(f"  SWAP scenario OK ({count} rows)")
        else:
            default_logger.info(f"  SWAP scenario WARN ({count} rows)")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class PocRunner:
    def __init__(
        self,
        catalog: str,
        raw_vault_schema: str ,
        dbt_project_dir: Path,
        models_output: Path ,
        metadata_path: Path ,
        generate_only: bool = False,
        skip_generate: bool = False,
        validate_only: bool = False,
    ):
        self.catalog = catalog
        self.raw_vault_schema = raw_vault_schema
        self.dbt_project_dir = dbt_project_dir
        self.metadata_path = metadata_path

        self.models_output = Path(models_output)
        self.generate_only = generate_only
        self.skip_generate = skip_generate
        self.validate_only = validate_only

        self.dbt = DbtService(dbt_project_dir=self.dbt_project_dir)
        self.generator = ModelGenerator(
            self.metadata_path,
            self.models_output,
        )
        self.validator = Validator(catalog=self.catalog, raw_vault_schema=self.raw_vault_schema)

    def run(self) -> None:
        start = time.time()

        default_logger.info("=" * 60)
        default_logger.info("DWA POC Runner — OOP version")
        default_logger.info("=" * 60)

        if self.validate_only:
            self.validator.validate()

        elif self.generate_only:
            self.generator.generate()

        else:
            if not self.skip_generate:
                default_logger.info("Starting model generation")
                self.generator.generate()

            self._run_layers()
            self.validator.validate()

        elapsed = time.time() - start
        default_logger.info(f"Done in {elapsed:.1f}s")

    def _run_layers(self) -> None:
        default_logger.info("Starting run for layers")
        self.dbt.run("tag:bronze")
        self.dbt.run("tag:staging")
        self.dbt.run("tag:raw_vault")





