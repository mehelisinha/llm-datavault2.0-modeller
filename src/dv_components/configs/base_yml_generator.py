from __future__ import annotations

from abc import ABC, abstractmethod
from logging import Logger
from pathlib import Path

import yaml

from shared.logger.default_logger import default_logger


class BaseYmlGenerator(ABC):
    """Shared YAML rendering and write behavior for dbt config generators."""

    def __init__(
        self,
        logger: Logger = default_logger,
        project_path: str | Path | None = None,
    ):
        self.logger = logger
        self.project_path = Path(project_path) if project_path else None

    @abstractmethod
    def _build_yaml_dict(self) -> dict:
        """Return the dictionary to be serialized into YAML."""

    @abstractmethod
    def _relative_output_path(self) -> Path:
        """Return the output path relative to the dbt project root."""

    def generate(self) -> str:
        """Return the YAML content as a string."""
        yaml_str = yaml.dump(
            self._build_yaml_dict(),
            sort_keys=False,
            default_flow_style=False,
        )
        self.logger.debug(f"Generated {self._relative_output_path().name}:\n{yaml_str}")
        return yaml_str

    def write(self, project_path: str | Path | None = None) -> Path:
        """Write YAML to disk and return the output path."""
        out_path = self._resolve_output_path(project_path)
        return self._write_content(out_path, self.generate())

    def _write_content(self, out_path: Path, content: str) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        self.logger.debug(f"  YML  -> {out_path}")
        return out_path

    def _resolve_output_path(self, project_path: str | Path | None) -> Path:
        root = Path(project_path) if project_path is not None else self.project_path
        if root is None:
            raise ValueError("project_path is required to write YAML output")
        return root / self._relative_output_path()
