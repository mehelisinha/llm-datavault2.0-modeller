"""
Base class for Data Vault components.
"""

from functools import cached_property
from typing import Any

from jinja2 import Environment

# ---------------------------------------------------------------------------
# Jinja2 rendering helpers
# ---------------------------------------------------------------------------


class TemplateRenderer:
    """
    Encapsulates the Jinja2 environment and rendering logic.

    Uses custom delimiters (<< >>, <% %>) to avoid conflicts with
    dbt's native Jinja2 syntax ({{ }}, {% %}).
    """

    @cached_property
    def env(self) -> Environment:
        return Environment(
            variable_start_string="<<",
            variable_end_string=">>",
            block_start_string="<%",
            block_end_string="%>",
        )

    def render(self, template: str, **kwargs: Any) -> str:
        return self.env.from_string(template).render(**kwargs)
