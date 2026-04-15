


from logging import Logger
from typing import Type

from shared.logger.default_logger import default_logger
from src.dv_components.components.base import DVBaseComponent
from src.dv_components.components.hub import Hub
from src.dv_components.components.link import Link
from src.dv_components.components.model import DVComponentModel
from src.dv_components.components.satellite import Satellite


class DVComponentFactory:
    _handlers:dict[str, type[DVBaseComponent]] = {
        "hub": Hub,
        "link": Link,
        "satellite": Satellite,
        "project": DBTProject
    }

    @classmethod
    def get(cls, model:DVComponentModel, logger:Logger = default_logger) -> Type[DVBaseComponent]:
        handler = cls._handlers.get(model.dv_type)
        if not handler:
            logger.error(f"No handler found for component type: {model.dv_type}")
            raise ValueError(f"No handler for component type: {model.dv_type}")
        return handler

    @classmethod
    def create(cls, model, source_models, logger:Logger = default_logger):
        component_cls = cls.get(model, logger)
        return component_cls(model=model, source_models=source_models, logger=logger)
