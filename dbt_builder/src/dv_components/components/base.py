"""
Base class for Data Vault components.
"""

from abc import ABC, abstractmethod
from functools import cached_property
from logging import Logger
from typing import Any, Dict

from shared.src.infra.file_manager.concrete.yml_handler import YamlHandler
from shared.src.logger.default_logger import default_logger
from dbt_builder.src.dv_components.helpers.template_renderer import TemplateRenderer
from dbt_builder.src.dv_components.pydantic_model.discriminator import SqlModels

# ---------------------------------------------------------------------------
# Configuration utilities
# ---------------------------------------------------------------------------


class _SqlConfigBuilder:
    """
    Builds the dbt config dict for a component.

    Applies base config, adds the component class name as a tag,
    and merges any component-specific overrides.
    """

    def build(
        self,
        base_config: Dict[str, Any],
        component_name: str,
        config_update: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Build the final config dict.

        Args:
            base_config:     Base config from the component (e.g. materialized, strategy).
            component_name:  Class name used as the auto-generated tag.
            config_update:   Optional overrides merged on top (e.g. unique_key).

        Returns:
            Final config dict ready for template rendering.
        """
        self._add_tag(base_config, component_name)
        self._merge(base_config, config_update)
        return base_config

    @staticmethod
    def _add_tag(config: Dict[str, Any], tag: str) -> None:
        config.setdefault("tags", [])
        if tag not in config["tags"]:
            config["tags"].append(tag)

    @staticmethod
    def _merge(config: Dict[str, Any], config_update: Dict[str, Any] | None) -> None:
        if config_update:
            config.update(config_update)

    @cached_property
    def config_macro(self):
        return """
<% macro render_config(config_options) %>
{{
    config(
<% for k, v in config_options.items() %>
        <<k>>=<<v|tojson>><%- if not loop.last %>,<% endif %>
<% endfor %>
    )
}}
<% endmacro %>
"""


# ---------------------------------------------------------------------------
# Formatting utilities
# ---------------------------------------------------------------------------


class _DbtFormatter:
    """Utility methods for formatting Python values into dbt/Jinja2 syntax."""

    @staticmethod
    def format_list(items: list[str]) -> str:
        """
        Format a Python list of strings into a dbt-compatible Jinja2 list literal.

        Example:
            ['stg_terminals']               -> "['stg_terminals']"
            ['stg_terminals', 'stg_orders'] -> "['stg_terminals', 'stg_orders']"
        """
        quoted = ", ".join(f"'{item}'" for item in items)
        return f"[{quoted}]"

    @staticmethod
    def format_list_as_dict(items: list[str]) -> str:
        """
        Format a Python list of strings into a dbt-compatible Jinja2 list literal.

        Example:
            ['stg_terminals']               -> "['stg_terminals']"
            ['stg_terminals', 'stg_orders'] -> "['stg_terminals', 'stg_orders']"
        """
        quoted = ", ".join(f"'{item}'" for item in items)
        return f"[{quoted}]"


# ---------------------------------------------------------------------------
# Base YML generator
# ---------------------------------------------------------------------------


class DVBaseYmlGenerator(ABC):
    """Base class for all DV generators — owns model and logger."""

    def __init__(self, model: SqlModels, logger: Logger = default_logger):
        self.model = model
        self.logger = logger

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement
    # ------------------------------------------------------------------
    @property
    @abstractmethod
    def _cols_for_yml(self) -> list[dict]:
        return []

    # ------------------------------------------------------------------
    # Template assembly
    # ------------------------------------------------------------------

    @property
    def _yaml_template(self) -> dict | None:
        """Build a dbt-compatible schema dict (version: 2, models: [...])."""
        cols = self._cols_for_yml
        if cols:
            return {
                "version": 2,
                "models": [
                    {
                        "name": self.model.name,
                        "description": self.model.description or "",
                        "columns": self._cols_for_yml,
                    }
                ],
            }
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_yml_str(self) -> str | None:
        """Generate the dbt YAML file content for this component."""
        yml = self._yaml_template
        if yml:
            name = (
                self.model.name if hasattr(self.model, "name") else self.model.dv_type
            )
            self.logger.debug(f"Generated YAML for '{name}':\n{yml}")
            return YamlHandler.generate(dic_content=yml, logger=self.logger)
        return None


# ---------------------------------------------------------------------------
# Base generator
# ---------------------------------------------------------------------------


class DVBaseComponentGenerator(DVBaseYmlGenerator, ABC):
    """
    Abstract base class for all Data Vault component generators.

    Subclasses must implement:
        - `_get_config`:       Base dbt config dict (materialized, strategy, etc.)
        - `_template_body`:    The dbt/Jinja2 template body (excluding config macro).
        - `_get_render_kwargs: All variables passed to the Jinja2 template at render time.

    The full rendering pipeline is:
        generate()
            └── _render(**_get_render_kwargs())
                    └── env.from_string(template).render(**kwargs)
                            └── template = _config_macro + _template_body
    """

    def __init__(self, model: SqlModels, logger: Logger = default_logger):
        super().__init__(model=model, logger=logger)
        self._renderer = TemplateRenderer()
        self._config_builder = _SqlConfigBuilder()
        self._formatter = _DbtFormatter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_sql_str(self) -> str:
        """Generate the dbt SQL file content for this component."""
        sql = self._render(**self._get_render_kwargs())
        name = self.model.name
        self.logger.debug(f"Generated SQL for '{name}':\n{sql}")
        return sql

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _get_sql_config(self) -> Dict[str, Any]:
        """Return the base dbt config dict for this component type."""

    @property
    @abstractmethod
    def _sql_template_body(self) -> str:
        """Return the dbt/Jinja2 template body (without the config macro header)."""

    @abstractmethod
    def _get_render_kwargs(self) -> Dict[str, Any]:
        """Return all variables to be injected into the template at render time."""

    @property
    @abstractmethod
    def _cols_for_yml(self) -> list[dict]:
        """Return the dbt/YAML template body (without the config macro header)."""

    # ------------------------------------------------------------------
    # Template assembly
    # ------------------------------------------------------------------

    @property
    def sql_template(self) -> str:
        """Full template: config macro + component body."""
        return self._config_builder.config_macro + self._sql_template_body

    # ------------------------------------------------------------------
    # Config building helpers
    # ------------------------------------------------------------------

    def _build_sql_config(
        self, config_update: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Build the final SQL config dict for this component.

        Args:
            config_update: Optional overrides (e.g. {"unique_key": "HK_TERMINAL"}).
        """
        return self._config_builder.build(
            base_config=self._get_sql_config(),
            component_name=self.__class__.__name__.lower(),
            config_update=config_update,
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, **kwargs: Any) -> str:
        """Render the full template with the given variables."""
        return self._renderer.render(self.sql_template, **kwargs)


# ---------------------------------------------------------------------------
# Base generator flavors
# ---------------------------------------------------------------------------


class DVBaseRawVaultComponent(DVBaseComponentGenerator, ABC):
    def _get_sql_config(self) -> Dict[str, Any]:
        """Get the dbt config for this component."""

        return {
            "materialized": "incremental",
            "incremental_strategy": "merge",
            "tags": ["raw_vault"],
        }

    @property
    def _default_cols_for_yml(self) -> list[dict]:
        return [
            {"name": self.model.src_pk, "tests": ["not_null", "unique"]},
            {"name": self.model.src_ldts, "tests": ["not_null"]},
        ]


class DVBaseStagingComponent(DVBaseComponentGenerator, ABC):
    def _get_sql_config(self) -> Dict[str, Any]:
        """Get the dbt config for this component."""

        return {
            "materialized": "view",
            "tags": ["staging"],
        }

    @property
    def _default_cols_for_yml(self) -> list[dict]:
        columns = []
        for hashed_col in self.model.hashed_columns:
            columns.append({"name": hashed_col.column_name, "tests": ["not_null"]})

        return columns
