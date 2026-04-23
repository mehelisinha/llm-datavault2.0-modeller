import os
from logging import Logger
from typing import Literal

from shared.src.infra.file_manager.file_manager import FileManager
from shared.src.logger.default_logger import default_logger
from dbt_builder.src.dv_components.components.factory.dv_component_factory import DVComponentFactory
from dbt_builder.src.dv_components.pydantic_model.discriminator import DvModels


class DVComponentManager:
    def __init__(
        self,
        model: DvModels,
        project_path: str,
        logger: Logger = default_logger,
    ) -> None:
        self.model = model
        self.project_path = project_path
        self.logger = logger
        self._output_dir = None

        self.component = DVComponentFactory.create(model=model, logger=logger)

    @property
    def output_dir(self) -> str:
        if self._output_dir is None:
            path = self.model.models_path
            self._output_dir = (
                os.path.join(self.project_path, path) if path else self.project_path
            )
        return self._output_dir

    def _get_output_path(self, ext: Literal["sql", "yml"]) -> str:
        if self.output_dir is None:
            self.logger.error("Output directory is not set.")
            raise ValueError("Output directory is not set.")
        return os.path.join(self.output_dir, f"{self.model.file_name}.{ext}")

    def _write_file(self, type: Literal["sql", "yml"]) -> str | None:
        if type == "sql":
            content = self.component.generate_sql_str()
        elif type == "yml":
            content = self.component.generate_yml_str()
        else:
            self.logger.error(f"Unsupported file type: {type}")
            raise ValueError(f"Unsupported file type: {type}")

        log_name = (
            self.model.file_name
            if hasattr(self.model, "file_name")
            else self.model.dv_type
        )
        if content:
            out_path = self._get_output_path(type)

            self.logger.debug(
                f"Writing {type.upper()} file for '{log_name}' at: {out_path}"
            )
            FileManager.write(out_path, content=content, overwrite=True)
            return out_path
        self.logger.warning(
            f"No content generated for '{log_name}' {type.upper()}. Skipping file write."
        )
        return None

    def write_files(self) -> dict[str, str | None]:
        """Write both SQL and YAML files for the component and return their paths."""
        paths = {}
        for ext in self.model.file_extension:
            if ext not in ["sql", "yml"]:
                self.logger.error(f"Unsupported file extension: {ext}")
                raise ValueError(f"Unsupported file extension: {ext}")
            paths[ext] = self._write_file(ext)
        return paths
