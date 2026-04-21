from __future__ import annotations

from logging import Logger
from pathlib import Path
from typing import Any

from shared.logger.default_logger import default_logger
from src.dv_components.configs.base_yml_generator import BaseYmlGenerator
from src.dv_components.configs.config_generator import DVConfigGenerator
from src.dv_components.configs.packages_yml import DVPackagesGenerator
from src.dv_components.configs.project_yml import DBTProject
from src.dv_components.configs.sources_yml import DBTSources
from src.dv_components.models.model import DVComponentModel, DVPackagesModel


class YmlGeneratorFactory:
    """Factory for choosing the correct concrete YAML generator."""

    _SCHEMA_COMPONENTS = {"hub", "link", "satellite", "eff_sat", "staging"}

    _handlers: dict[str, type[BaseYmlGenerator]] = {
        **dict.fromkeys(_SCHEMA_COMPONENTS, DVConfigGenerator),
        "dv_project": DBTProject,
        "sources": DBTSources,
        "packages": DVPackagesGenerator,
    }

    _PROJECT_PATH_REQUIRED = {"packages", *_SCHEMA_COMPONENTS}

    @classmethod
    def _resolve_type_key(cls, model: DVComponentModel | DVPackagesModel) -> str:
        if isinstance(model, DVPackagesModel):
            return "packages"
        return model.dv_type

    @classmethod
    def get(
        cls,
        model: DVComponentModel | DVPackagesModel,
        logger: Logger = default_logger,
    ) -> type[BaseYmlGenerator]:
        type_key = cls._resolve_type_key(model)
        handler = cls._handlers.get(type_key)
        if handler is None:
            logger.error(f"No YAML generator registered for model type: {type_key}")
            raise ValueError(f"No YAML generator registered for model type: {type_key}")
        return handler

    @classmethod
    def create(
        cls,
        model: DVComponentModel | DVPackagesModel,
        logger: Logger = default_logger,
        project_path: str | Path | None = None,
    ) -> BaseYmlGenerator:
        type_key = cls._resolve_type_key(model)
        handler = cls.get(model=model, logger=logger)

        if type_key in cls._PROJECT_PATH_REQUIRED and project_path is None:
            raise ValueError(
                f"project_path is required for '{type_key}' YAML generator"
            )

        init_kwargs: dict[str, Any] = {"model": model, "logger": logger}
        if type_key in cls._PROJECT_PATH_REQUIRED:
            init_kwargs["project_path"] = project_path

        return handler(**init_kwargs)
