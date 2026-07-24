"""
DBTBuilder — orchestrates SQL and config generation for a full dbt Data Vault project.

Given a metadata YAML path and an output directory, DBTBuilder:
  1. Writes a .sql file for every hub, link, satellite, and eff_sat.
  2. Writes a .yml metadata file for every component.
  3. Writes dbt_project.yml at the project root.
"""

from __future__ import annotations

import shutil
import sys
from logging import Logger
from pathlib import Path

if __package__ in (None, ""):
    # Support running this file directly:
    # python dbt_builder/src/runners/dbt_builder.py
    # by exposing the repository root on sys.path.
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from dbt_builder.src.dv_components.manager.dv_component_manager import (
    DVComponentManager,
)
from dbt_builder.src.dv_components.pydantic_model.discriminator import DvModels
from dbt_builder.src.runners.metadata import Metadata
from shared.src.logger.default_logger import default_logger


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
        self.cleanup_output_location()
        for key, model_component_list in self._get_component_models().items():
            for component_model in model_component_list:
                self._write_component_files(component_model, key=key)

        self._logger.info("Build complete.")

    def cleanup_output_location(self) -> Path:
        """Remove and recreate the build output directory."""
        output_dir = Path(self._output_path)

        # Safety guard to avoid accidental deletion of filesystem roots.
        if output_dir.resolve() == output_dir.anchor:
            raise ValueError(f"Refusing to clean unsafe output path: {output_dir}")

        if output_dir.exists():
            self._logger.info(f"Cleaning output directory: {output_dir}")
            shutil.rmtree(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------
    def _get_component_models(self) -> dict[str, list[DvModels]]:
        return self._metadata.get_all_component_models()

    def _write_component_files(
        self, component_model: DvModels, key: str = "dv"
    ) -> None:
        component = DVComponentManager(
            model=component_model, project_path=self._output_path, logger=self._logger
        )
        paths = component.write_files()
        self._logger.debug(f"  {key}  → {paths}")


if __name__ == "__main__":
    from pathlib import Path

    # parents: [0]=runners [1]=src [2]=dbt_builder [3]=repo root. The metadata and
    # output live at the repo root, so index [3] (was [2], which pointed one level
    # too shallow and raised FileNotFoundError).
    repo_root = Path(__file__).parents[3]
    yaml_path = repo_root / "poc" / "metadata" / "iec_cim_metadata.yaml"

    builder = DBTBuilder(
        metadata_path=yaml_path,
        output_path=repo_root / "output" / "iec_dv2",
    )
    # models = builder._get_component_models()
    # print(f"meta_models: ({models.__class__.__name__}):")
    builder.build()
