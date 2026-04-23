"""
Generates packages.yml for a dbt project from a DVPackagesModel.
"""

from logging import Logger

from shared.src.logger.default_logger import default_logger
from dbt_builder.src.dv_components.components.project_level.base import DVProjYmlBaseGenerator
from dbt_builder.src.dv_components.pydantic_model.proj_level.dv_yml import DVPackagesModel


class PackagesComponent(DVProjYmlBaseGenerator):
    """Generates packages.yml content from a DVPackagesModel."""

    def __init__(
        self,
        model: DVPackagesModel,
        logger: Logger = default_logger,
    ):
        super().__init__(model=model, logger=logger)
        self.model = model

    @property
    def _yaml_template(self) -> dict:
        return {"packages": [p.model_dump() for p in self.model.packages]}
