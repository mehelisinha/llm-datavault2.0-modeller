from logging import Logger
from typing import Type

from shared.logger.default_logger import default_logger
from src.dv_components.models.base import DVComponentBaseGenerator
from src.dv_components.models.hub import Hub
from src.dv_components.models.link import Link
from src.dv_components.models.macro import Macro
from src.dv_components.models.model import DVComponentModel
from src.dv_components.models.satellite import SatelliteFactory
from src.dv_components.models.staging import Staging


class DVComponentFactory:
    _handlers: dict[str, type[DVComponentBaseGenerator | SatelliteFactory]] = {
        "hub": Hub,
        "link": Link,
        "satellite": SatelliteFactory,
        "eff_sat": SatelliteFactory,
        "staging": Staging,
        "macro": Macro,
    }

    @classmethod
    def get(
        cls, model: DVComponentModel, logger: Logger = default_logger
    ) -> Type[DVComponentBaseGenerator | SatelliteFactory]:
        handler = cls._handlers.get(model.dv_type)
        if not handler:
            logger.error(f"No handler found for component type: {model.dv_type}")
            raise ValueError(f"No handler for component type: {model.dv_type}")
        return handler

    @classmethod
    def create(cls, model: DVComponentModel, logger: Logger = default_logger):
        component_cls = cls.get(model, logger)
        return component_cls(model=model, logger=logger)
