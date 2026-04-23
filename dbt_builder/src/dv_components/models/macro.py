"""
Hub component for Data Vault v2.
"""

from abc import abstractmethod
from logging import Logger
from typing import Any

from dv_components.components.TBD_model import DVComponentModel, MacroModel

from dbt_builder.src.dv_components.components.base import DVMBaseComponentGenerator


class Macro(DVMBaseComponentGenerator):
    """Base class for dbt macro generators."""

    def __init__(self, model: Any, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model.meta, MacroModel):
            raise ValueError(f"Expected MacroModel, got {type(model.meta)}")
        self.macro_model: MacroModel = model.meta

    def _get_render_kwargs(self) -> dict:
        return dict()

    @property
    @abstractmethod
    def _sql_template_body(self) -> str:
        """Return the macro body template."""

    def _get_sql_config(self) -> dict[str, Any]:
        return {}


class GenerateSchemaNameMacro(Macro):
    @property
    def _sql_template_body(self) -> str:
        return """\
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
"""


class DropTableMacro(Macro):
    @property
    def _sql_template_body(self) -> str:
        return """\
{% macro drop_model(model_name, schema_name) -%}
    {% set query %}
        DROP TABLE IF EXISTS {{ schema_name }}.{{ model_name }}
    {% endset %}
    {% do run_query(query) %}
{%- endmacro %}
"""


class MacroFactory:
    """Create concrete macro generators by macro model name."""

    _handlers = {
        "generate_schema_name": GenerateSchemaNameMacro,
        "drop_model": DropTableMacro,
        "drop_table": DropTableMacro,
    }

    def __new__(cls, model: Any, logger: Logger):
        macro_name = model.name.strip().lower()
        handler = cls._handlers.get(macro_name)
        if not handler:
            supported = ", ".join(sorted(cls._handlers))
            raise ValueError(
                f"No macro handler for '{model.name}'. Supported macros: {supported}"
            )
        return handler(model=model, logger=logger)


if __name__ == "__main__":
    from shared.src.logger.default_logger import default_logger

    macro_model = MacroModel()

    model = DVComponentModel(name="generate_schema_name", meta=macro_model)
    macro_generator: Any = MacroFactory(model=model, logger=default_logger)
    sql = macro_generator.generate()
