"""
Generates packages.yml for a dbt project from a DVPackagesModel.
"""

from logging import Logger
from pathlib import Path

import yaml

from src.dv_components.components.model import DVPackagesModel
from shared.logger.default_logger import default_logger


class DVPackagesGenerator:
    """Generates packages.yml content from a DVPackagesModel."""

    def __init__(
        self,
        model: DVPackagesModel,
        project_path: str | Path,
        logger: Logger = default_logger,
    ):
        self.model = model
        self.project_path = Path(project_path)
        self.logger = logger

    def generate(self) -> str:
        """Write packages.yml to the project root and return the file path."""
        out_path = self.project_path / "packages.yml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        content = yaml.dump(
            {"packages": [p.model_dump() for p in self.model.packages]},
            sort_keys=False,
            default_flow_style=False,
        )
        out_path.write_text(content, encoding="utf-8")
        self.logger.debug(f"Generated packages.yml → {out_path}")
        return str(out_path)
