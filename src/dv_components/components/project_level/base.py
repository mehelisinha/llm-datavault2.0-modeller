"""
Base class for Data Vault components.
"""

from abc import ABC, abstractmethod
from logging import Logger

from shared.infra.file_manager.concrete.yml_handler import YamlHandler
from shared.logger.default_logger import default_logger
from src.dv_components.pydantic_model.discriminator import ProjectModels

# ---------------------------------------------------------------------------
# Base YML generator
# ---------------------------------------------------------------------------


class DVProjYmlBaseGenerator(ABC):
    """Base class for all DV generators — owns model and logger."""

    def __init__(self, model: ProjectModels, logger: Logger = default_logger):
        self.model = model
        self.logger = logger

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def _yaml_template(self) -> dict | None:
        """Build a dbt-compatible schema dict (version: 2, models: [...])."""
        ...

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_yml_str(self) -> str | None:
        """Generate the dbt Project level YAML file content for this component."""
        if self._yaml_template is None:
            return None
        return YamlHandler.generate_with_jinja(self._yaml_template, logger=self.logger)
