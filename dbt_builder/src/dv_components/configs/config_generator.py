"""
Data Vault YAML configuration generator.

Generates dbt schema YAML files (version: 2 / models: [...]) for hub/link/satellite
from Data Vault components, compatible with dbt's model documentation format.
"""

from abc import ABC, abstractmethod
from logging import Logger
from pathlib import Path

from dv_components.components.TBD_model import DVComponentModel

from shared.src.infra.file_manager.concrete.yml_handler import YamlHandler
from shared.src.infra.file_manager.file_manager import FileManager
from shared.src.logger.default_logger import default_logger


class DVBaseYMLGenerator(ABC):
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

    def _relative_output_path(self) -> Path:
        base_path = self.model.base_models_path
        if not base_path:
            return Path(f"{self.model.name}.yml")
        return Path(base_path) / f"{self.model.name}.yml"

    def write(self):
        """Write a dbt schema YAML file and return the file path."""
        output_path = self._relative_output_path()
        yml_dict = self._build_yaml_dict()
        yml_str = YamlHandler.generate(yml_dict, logger=self.logger)
        return FileManager.write(
            file_path=output_path, content=yml_str, logger=self.logger
        )

    @abstractmethod
    def _build_yaml_dict(self) -> dict:
        """Build a dbt-compatible schema dict (version: 2, models: [...])."""
        ...
        # return {
        #     "version": 2,
        #     "models": [
        #         {
        #             "name": self.model.name,
        #             "description": self.model.description or "",
        #             "columns": self._build_columns(),
        #         }
        #     ],
        # }

    # @abstractmethod
    # def _build_columns(self) -> list[dict]:
    #     """Return standard Data Vault column tests for this model type."""
    #     pass


class DVConfigGenerator(DVBaseYMLGenerator):
    """Generate dbt-compatible schema YAML for a Data Vault component."""

    def __init__(
        self,
        model: DVComponentModel,
        project_path: str,
        logger: Logger = default_logger,
    ):
        super().__init__(model=model, project_path=project_path, logger=logger)

    def _relative_output_path(self) -> Path:
        base_path = self.model.base_models_path
        if not base_path:
            return Path(f"{self.model.name}.yml")
        return Path(base_path) / f"{self.model.name}.yml"

    def write(self, project_path: str | Path | None = None) -> str:
        """Write a dbt schema YAML file and return the file path."""
        return str(super().write(output_path=project_path))

    # @tag:to_do: move this to its own class inside config dir: Schema
    def _build_yaml_dict(self) -> dict:
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
            columns.append({"name": meta.src_pk, "tests": ["not_null", "unique"]})
            columns.append({"name": meta.src_ldts, "tests": ["not_null"]})

        if dv_type == "satellite":
            columns.append({"name": meta.src_hashdiff, "tests": ["not_null"]})

        if dv_type == "eff_sat" and meta.src_dfk != meta.src_pk:
            columns.append({"name": meta.src_dfk, "tests": ["not_null"]})

        if dv_type == "staging":
            for hashed_col in meta.hashed_columns:
                columns.append({"name": hashed_col.column_name, "tests": ["not_null"]})

        return columns
