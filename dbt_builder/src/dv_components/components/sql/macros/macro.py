"""
Macro component for Data Vault v2.
"""

from abc import abstractmethod
from logging import Logger
from typing import Any

from dbt_builder.src.dv_components.components.base import DVBaseComponentGenerator
from dbt_builder.src.dv_components.pydantic_model.sql.macro import MacroModel


class BaseMacroComponent(DVBaseComponentGenerator):
    """Base class for dbt macro generators."""

    def __init__(self, model: MacroModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model, MacroModel):
            raise ValueError(f"Expected Macro, got {type(model)}")
        self.macro_model: MacroModel = model

    def _get_render_kwargs(self) -> dict:
        return dict()

    @property
    @abstractmethod
    def _sql_template_body(self) -> str:
        """Return the macro body template."""

    def _get_sql_config(self) -> dict[str, Any]:
        return {}

    @property
    def _cols_for_yml(self) -> list[dict]:
        return []  # Macros don't have columns, but we need to return something for the YAML generation in the base class.


class GenerateSchemaNameMacro(BaseMacroComponent):
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


class DropTableMacro(BaseMacroComponent):
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
