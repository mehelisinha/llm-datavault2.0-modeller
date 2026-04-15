


from logging import Logger
from typing import Optional

from src.dv_components.factory.registry import BaseComponent


class DVComponentFactory:

    @classmethod
    def create(
        cls,
        model,
        source_models=None,
        logger: Optional[Logger] = None
    ) -> BaseComponent:
        """
        Create a component instance based on model.dv_type.
        """
        dv_type = getattr(model, "dv_type", None)

        if not dv_type:
            raise ValueError("Model is missing 'dv_type'")

        component_cls = BaseComponent.registry.get(dv_type)

        if not component_cls:
            if logger:
                logger.error(f"No component registered for type: {dv_type}")
            raise ValueError(f"No component registered for type: {dv_type}")

        return component_cls(
            model=model,
            source_models=source_models or []
        )


# usage:
# component = DVComponentFactory.create(
#     model=my_model,
#     source_models=["stg_customer"]
# )

# sql = ComponentRenderer.sql(component)
# yml = ComponentRenderer.yml(component)
