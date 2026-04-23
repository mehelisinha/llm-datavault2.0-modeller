"""
Base class for Data Vault components.
"""

from abc import ABC, abstractmethod
from logging import Logger

import yaml

from dbt_builder.src.dv_components.pydantic_model.discriminator import ProjectModels
from shared.src.logger.default_logger import default_logger

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
        yaml_str = yaml.dump(
            self._yaml_template,
            sort_keys=False,
            default_flow_style=False,
        )
        self.logger.debug(f"Generated :\n{yaml_str}")
        return yaml_str
