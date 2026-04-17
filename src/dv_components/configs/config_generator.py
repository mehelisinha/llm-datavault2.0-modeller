"""
Data Vault YAML configuration generator.

Generates dbt schema YAML files (version: 2 / models: [...]) for hub/link/satellite
from Data Vault components, compatible with dbt's model documentation format.
"""

import os
from logging import Logger
from pathlib import Path

import yaml

from src.dv_components.components.model import DVComponentModel
from shared.logger.default_logger import default_logger


class DVConfigGenerator:
    """Generate dbt-compatible schema YAML for a Data Vault component."""

    def __init__(
        self,
        model: DVComponentModel,
        project_path: str,
        logger: Logger = default_logger,
    ):
        self.model = model
        self.project_path = project_path
        self.logger = logger

    def generate(self) -> str:
        """Write a dbt schema YAML file and return the file path."""
        path = self.model.base_models_path
        output_dir = os.path.join(self.project_path, path) if path else self.project_path
        out_path = Path(output_dir) / f"{self.model.name}.yml"

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            yaml.dump(self._build_schema_dict(), sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        return str(out_path)

    def _build_schema_dict(self) -> dict:
        """Build a dbt-compatible schema dict (version: 2, models: [...])."""
        return {
            "version": 2,
            "models": [
                {
                    "name": self.model.name,
                    "description": self.model.description or "",
                    "columns": self._build_columns(),
                }
            ],
        }

    def _build_columns(self) -> list[dict]:
        """Return standard Data Vault column tests for this model type."""
        meta = self.model.meta
        dv_type = meta.dv_type
        columns = []

        if dv_type in ("hub", "link", "satellite", "eff_sat"):
            columns.append(
                {"name": meta.src_pk, "tests": ["not_null", "unique"]}
            )
            columns.append(
                {"name": meta.src_ldts, "tests": ["not_null"]}
            )

        if dv_type == "satellite":
            columns.append(
                {"name": meta.src_hashdiff, "tests": ["not_null"]}
            )

        if dv_type == "eff_sat" and meta.src_dfk != meta.src_pk:
            columns.append(
                {"name": meta.src_dfk, "tests": ["not_null"]}
            )

        if dv_type == "staging":
            for hashed_col in meta.hashed_columns:
                columns.append({"name": hashed_col.column_name, "tests": ["not_null"]})

        return columns
