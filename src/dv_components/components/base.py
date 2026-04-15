"""
Base class for Data Vault components.
"""

from abc import ABC, abstractmethod
from functools import cached_property
from logging import Logger
from typing import Any, Dict

from shared.logger.default_logger import default_logger
from src.dv_components.components.model import DVComponentModel
from src.dv_components.components.template_renderer import TemplateRenderer

# ---------------------------------------------------------------------------
# Configuration utilities
# ---------------------------------------------------------------------------


class _ConfigBuilder:
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


# ---------------------------------------------------------------------------
# Base generator
# ---------------------------------------------------------------------------


class DVComponentBaseGenerator(ABC):
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

    _renderer = TemplateRenderer()
    _config_builder = _ConfigBuilder()
    _formatter = _DbtFormatter()

    def __init__(self, model: DVComponentModel, logger: Logger = default_logger):
        self.model = model
        self.logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> str:
        """Generate the dbt SQL file content for this component."""
        sql = self._render(**self._get_render_kwargs())
        self.logger.debug(f"Generated SQL for '{self.model.name}':\n{sql}")
        return sql

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _get_config(self) -> Dict[str, Any]:
        """Return the base dbt config dict for this component type."""

    @property
    @abstractmethod
    def _template_body(self) -> str:
        """Return the dbt/Jinja2 template body (without the config macro header)."""

    @abstractmethod
    def _get_render_kwargs(self) -> Dict[str, Any]:
        """Return all variables to be injected into the template at render time."""

    # ------------------------------------------------------------------
    # Template assembly
    # ------------------------------------------------------------------

    @property
    def template(self) -> str:
        """Full template: config macro + component body."""
        return self._config_builder.config_macro + self._template_body

    # ------------------------------------------------------------------
    # Config building helpers
    # ------------------------------------------------------------------

    def _build_config(
        self, config_update: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Build the final config dict for this component.

        Args:
            config_update: Optional overrides (e.g. {"unique_key": "HK_TERMINAL"}).
        """
        return self._config_builder.build(
            base_config=self._get_config(),
            component_name=self.__class__.__name__.lower(),
            config_update=config_update,
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, **kwargs: Any) -> str:
        """Render the full template with the given variables."""
        return self._renderer.render(self.template, **kwargs)


# ---------------------------------------------------------------------------
# Base generator flavors
# ---------------------------------------------------------------------------


class DVBaseRawVaultComponent(DVComponentBaseGenerator):
    def _get_config(self) -> Dict[str, Any]:
        """Get the dbt config for this component."""

        return {
            "materialized": "incremental",
            "incremental_strategy": "merge",
            "tags": ["raw_vault"],
        }


class DVBaseStagingComponent(DVComponentBaseGenerator):
    def _get_config(self) -> Dict[str, Any]:
        """Get the dbt config for this component."""

        return {
            "materialized": "view",
            "tags": ["staging"],
        }
