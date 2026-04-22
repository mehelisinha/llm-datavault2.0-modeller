from logging import Logger
from typing import Any

from shared.logger.default_logger import default_logger
from src.dv_components.components.base import DVBaseComponentGenerator
from src.dv_components.components.project_level.packages_yml import PackagesComponent
from src.dv_components.components.project_level.profiles_yml import ProfilesComponent
from src.dv_components.components.project_level.project_yml import ProjectComponent
from src.dv_components.components.project_level.sources_yml import SourcesComponent
from src.dv_components.components.sql.macros.macro_factory import MacroComponentFactory
from src.dv_components.components.sql.raw_vault.hub import HubComponent
from src.dv_components.components.sql.raw_vault.link import LinkComponent
from src.dv_components.components.sql.raw_vault.satellite import (
    EffSatComponent,
    SatComponent,
)
from src.dv_components.components.sql.staging.staging import StagingComponent
from src.dv_components.pydantic_model.discriminator import DvModels


class DVComponentFactory:
    _handlers: dict[str, Any] = {
        # --- SQL Models ---#
        "hub": HubComponent,
        "link": LinkComponent,
        "satellite": SatComponent,
        "eff_sat": EffSatComponent,
        "staging": StagingComponent,
        "macro": MacroComponentFactory,
        # --- Proj Models ---#
        "project": ProjectComponent,
        "packages": PackagesComponent,
        "sources": SourcesComponent,
        "profiles": ProfilesComponent,
    }

    @classmethod
    def _get(cls, model: DvModels, logger: Logger = default_logger) -> Any:
        handler = cls._handlers.get(model.dv_type)
        if not handler:
            logger.error(f"No handler found for component type: {model.dv_type}")
            raise ValueError(f"No handler for component type: {model.dv_type}")
        return handler

    @classmethod
    def create(
        cls, model: DvModels, logger: Logger = default_logger
    ) -> DVBaseComponentGenerator:
        component_cls = cls._get(model, logger)
        return component_cls(model=model, logger=logger)
