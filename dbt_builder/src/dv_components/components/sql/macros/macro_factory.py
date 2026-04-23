"""
Hub component for Data Vault v2.
"""

from logging import Logger
from typing import Any

from dbt_builder.src.dv_components.components.sql.macros.macro import (
    DropTableMacro,
    GenerateSchemaNameMacro,
)
from dbt_builder.src.dv_components.pydantic_model.sql.macro import MacroModel


class MacroComponentFactory:
    """Create concrete macro generators by macro model name."""

    _handlers = {
        "generate_schema_name": GenerateSchemaNameMacro,
        "drop_table": DropTableMacro,
    }

    def __new__(cls, model: MacroModel, logger: Logger):
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

    model = MacroModel(name="generate_schema_name")
    macro_generator: Any = MacroComponentFactory(model=model, logger=default_logger)
    sql = macro_generator.generate_sql_str()
