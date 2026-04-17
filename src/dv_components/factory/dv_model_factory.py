from logging import Logger
from typing import Type

from shared.logger.default_logger import default_logger
from src.dv_components.components.base import DVComponentBaseGenerator
from src.dv_components.components.hub import Hub
from src.dv_components.components.link import Link
from src.dv_components.components.model import DVComponentModel
from src.dv_components.components.satellite import Satellite
from src.dv_components.components.staging import Staging

# from src.dv_components.configs.project_yml import dbt_project


class DVComponentFactory:
    _handlers: dict[str, type[DVComponentBaseGenerator]] = {
        "hub": Hub,
        "link": Link,
        "satellite": Satellite,
        "staging": Staging,
        # "project": DBTProject
    }

    @classmethod
    def get(
        cls, model: DVComponentModel, logger: Logger = default_logger
    ) -> Type[DVComponentBaseGenerator]:
        handler = cls._handlers.get(model.dv_type)
        if not handler:
            logger.error(f"No handler found for component type: {model.dv_type}")
            raise ValueError(f"No handler for component type: {model.dv_type}")
        return handler

    @classmethod
    def create(cls, model, source_models, logger: Logger = default_logger):
        component_cls = cls.get(model, logger)
        return component_cls(model=model, logger=logger)
