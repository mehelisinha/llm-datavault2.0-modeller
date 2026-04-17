from abc import ABC
from logging import Logger
from typing import Dict, Type

from shared.logger.default_logger import default_logger
from src.dv_components.models.base import DVBaseComponent
from src.dv_components.models.hub import Hub
from src.dv_components.models.link import Link
from src.dv_components.models.model import DVComponentModel
from src.dv_components.models.satellite import Satellite


class BaseComponent(ABC):
    """Base class for all DV components."""

    registry: Dict[str, Type["BaseComponent"]] = {}

    def __init__(self, model, source_models):
        self.model = model
        self.source_models = source_models

    @classmethod
    def register(cls, name: str):
        """Decorator to register components automatically."""

        def decorator(subclass: Type["BaseComponent"]):
            cls.registry[name] = subclass
            return subclass

        return decorator


@BaseComponent.register("hub")
class HubComponent(BaseComponent):
    pass


@BaseComponent.register("link")
class LinkComponent(BaseComponent):
    pass


@BaseComponent.register("satellite")
class SatelliteComponent(BaseComponent):
    pass


@BaseComponent.register("project")
class ProjectComponent(BaseComponent):
    pass


class DVComponentFactory:
    _handlers: dict[str, type[DVBaseComponent]] = {
        "hub": Hub,
        "link": Link,
        "satellite": Satellite,
        "project": DBTProject,
    }

    @classmethod
    def get(
        cls, model: DVComponentModel, logger: Logger = default_logger
    ) -> Type[DVBaseComponent]:
        handler = cls._handlers.get(model.dv_type)
        if not handler:
            logger.error(f"No handler found for component type: {model.dv_type}")
            raise ValueError(f"No handler for component type: {model.dv_type}")
        return handler

    @classmethod
    def create(cls, model, source_models, logger: Logger = default_logger):
        component_cls = cls.get(model, logger)
        return component_cls(model=model, source_models=source_models, logger=logger)
