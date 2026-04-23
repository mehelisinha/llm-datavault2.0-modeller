"""
Generates packages.yml for a dbt project from a DVPackagesModel.
"""

from logging import Logger
from pathlib import Path

from dv_components.components.TBD_model import DVPackagesModel
from dv_components.TBD_configs.TBD_base_yml_generator import BaseYmlGenerator

from shared.src.logger.default_logger import default_logger


class DVPackagesGenerator(BaseYmlGenerator):
    """Generates packages.yml content from a DVPackagesModel."""

    def __init__(
        self,
        model: DVPackagesModel,
        project_path: str | Path,
        logger: Logger = default_logger,
    ):
        super().__init__(logger=logger, project_path=project_path)
        self.model = model

    def generate(self) -> str:
        """Return packages.yml content as a YAML string."""
        return super().generate()

    def _build_yaml_dict(self) -> dict:
        return {"packages": [p.model_dump() for p in self.model.packages]}

    def _relative_output_path(self) -> Path:
        return Path("packages.yml")
