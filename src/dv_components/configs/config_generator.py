"""
Data Vault YAML configuration generator.

Generates dbt model metadata files for hub/link/satellite from Data Vault components.
"""

import os
from logging import Logger

from dv_components.components.model import DVComponentModel
from shared.infra.file_manager.file_manager import FileManager
from shared.logger.default_logger import default_logger


class DVBaseComponent(ABC):
    """Abstract base class for Data Vault components."""

    def __init__(self, model:DVComponentModel, source_models: list[str], logger:Logger = default_logger):
        self.model = model
        self.source_models = source_models
        self.logger = logger

class DVConfigGenerator:
    """Generate YAML model metadata for Data Vault objects."""

    def __init__(self, model:DVComponentModel,project_path: str, logger:Logger=default_logger):
        self.model = model
        self.project_path = project_path
        self.logger = logger

    def generate_yaml(self) -> str:
        path = self.model.base_models_path
        if path:
            output_dir = os.path.join(self.project_path, path, f"{self.model.dv_type}s")
        else:
            output_dir = self.project_path
        out_path = os.path.join(output_dir, f"{self.model.name}.yml")
        payload = self.model.model_dump()
        FileManager.write(file_path=out_path, content=str(payload), logger=self.logger, overwrite=True)
        return out_path

