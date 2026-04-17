"""
DBTBuilder — orchestrates SQL and config generation for a full dbt Data Vault project.

Given a metadata YAML path and an output directory, DBTBuilder:
  1. Writes a .sql file for every hub, link, satellite, and eff_sat.
  2. Writes a .yml metadata file for every component.
  3. Writes dbt_project.yml at the project root.
"""

from __future__ import annotations

from logging import Logger
from pathlib import Path

from shared.logger.default_logger import default_logger
from src.dv_components.configs.config_generator import DVConfigGenerator
from src.dv_components.configs.packages_yml import DVPackagesGenerator
from src.dv_components.configs.project_yml import DBTProject
from src.dv_components.configs.sources_yml import DBTSources
from src.dv_components.factory.dv_component_manager import DVComponentManager
from src.dv_components.models.model import (
    DVComponentModel,
    DVSourceModel,
    MacroModel,
    TableConfig,
)
from src.runners.metadata import Metadata


class DBTBuilder:
    """
    Generates a complete dbt project structure from a DWA metadata YAML.

    Args:
        metadata_path:  Path to the DWA YAML metadata file.
        output_path:    Root directory of the dbt project to generate into.
        logger:         Optional logger instance.

    Usage::

        builder = DBTBuilder(
            metadata_path="config/iec_cim_metadata.yaml",
            output_path="output/iec_dv2",
        )
        builder.build()
    """

    def __init__(
        self,
        metadata_path: str | Path,
        output_path: str | Path,
        logger: Logger = default_logger,
    ):
        self._metadata = Metadata(metadata_path)
        self._output_path = str(output_path)
        self._logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Generate SQL files, component YAML metadata, dbt_project.yml, packages.yml, sources.yml."""
        self._logger.info(
            f"Building dbt project for '{self._metadata.system_name}' "
            f"→ {self._output_path}"
        )
        self._write_component_files()
        self._write_project_yml()
        self._write_packages_yml()
        self._write_macros()
        self._write_sources_yml()
        self._logger.info("Build complete.")

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _write_component_files(self) -> None:
        for model in self._metadata.get_all_component_models():
            sql_path = DVComponentManager.write_sql_file(
                model=model,
                project_path=self._output_path,
                logger=self._logger,
            )
            self._logger.debug(f"  SQL  → {sql_path}")

            yml_path = DVConfigGenerator(
                model=model,
                project_path=self._output_path,
                logger=self._logger,
            ).write()
            self._logger.debug(f"  YML  → {yml_path}")

    def _write_project_yml(self) -> None:
        project_model = self._metadata.get_project_model()
        dbt_proj = DBTProject(model=project_model, logger=self._logger)
        yaml_content = dbt_proj.generate()

        output_path = dbt_proj.write(
            project_path=self._output_path, yaml_content=yaml_content
        )
        self._logger.debug(f"  PRJ  → {output_path}")

    def _write_packages_yml(self) -> None:
        packages_model = self._metadata.get_packages_model()
        pkg_path = DVPackagesGenerator(
            model=packages_model,
            project_path=self._output_path,
            logger=self._logger,
        ).generate()
        self._logger.debug(f"  PKG  → {pkg_path}")

    def _write_macros(self) -> None:
        macro_model = MacroModel()
        model = DVComponentModel(name="generate_schema_name", meta=macro_model)
        sql_path = DVComponentManager.write_sql_file(
            model=model,
            project_path=self._output_path,
            logger=self._logger,
        )
        self._logger.debug(f"  MCR  → {sql_path}")

    def _write_sources_yml(self) -> None:
        """Generate models/staging/sources.yml from system metadata + staging entries."""
        system = self._metadata.system
        model = DVSourceModel(
            name=system.get("schema"),
            database=system.get("catalog"),
            schema=system.get("schema"),
            tables=[
                TableConfig(name=entry["source_table"])
                for entry in self._metadata._config.get("staging", [])
                if "source_table" in entry
            ],
        )

        model = DVComponentModel(name="iec_dv2", meta=model)
        dbt_sources = DBTSources(model=model, logger=default_logger)
        yaml_content = dbt_sources.generate()
        out_path = dbt_sources.write(
            project_path=self._output_path,
            yaml_content=yaml_content,
        )
        self._logger.debug(f"  SRC  → {out_path}")


if __name__ == "__main__":
    from pathlib import Path

    builder = DBTBuilder(
        metadata_path=Path(__file__).parents[2]
        / "poc"
        / "metadata"
        / "iec_cim_metadata.yaml",
        output_path=Path(__file__).parents[2] / "output" / "iec_dv2",
    )
    builder.build()
