"""
Hub component for Data Vault v2.
"""

from logging import Logger
from typing import Any

from src.dv_components.models.base import DVComponentBaseGenerator
from src.dv_components.models.model import DVComponentModel, MacroModel


class Macro(DVComponentBaseGenerator):
    """Data Vault Hub component."""

    def __init__(self, model: DVComponentModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model.meta, MacroModel):
            raise ValueError(f"Expected HubModel, got {type(model.meta)}")
        self.hub_model: MacroModel = model.meta

    def _get_render_kwargs(self) -> dict:
        return dict()

    @property
    def _template_body(self) -> str:
        return """\
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
"""

    def _get_config(self) -> dict[str, Any]:
        return {}


if __name__ == "__main__":
    from shared.logger.default_logger import default_logger

    macro_model = MacroModel()

    model = DVComponentModel(name="generate_schema_name", meta=macro_model)
    macro = Macro(model=model, logger=default_logger)
    sql = macro.generate()
