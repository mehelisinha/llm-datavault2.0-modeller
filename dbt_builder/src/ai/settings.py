"""Typed configuration for the DWA AI layer.

Loads settings from environment variables (prefix ``DWA_AI_``) and an
optional ``.env`` file at the repository root. Use :func:`get_settings`
to obtain a cached singleton instance.

Example:
    >>> from dbt_builder.src.ai.settings import get_settings
    >>> cfg = get_settings()
    >>> cfg.azure_openai_endpoint
    'https://dwa-foundry-...openai.azure.com/'
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root (.env lives here, two levels up from this file's package root)
_REPO_ROOT = Path(__file__).resolve().parents[3]


class AISettings(BaseSettings):
    """Configuration for Azure AI Foundry, OpenAI, Search, and observability.

    All fields are loaded from environment variables prefixed with ``DWA_AI_``.
    A ``.env`` file at the repository root is also read if present.
    """

    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="DWA_AI_",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Azure subscription / resource metadata ────────────────────────────────
    azure_subscription_id: str = Field(..., description="Azure subscription GUID")
    azure_resource_group: str = Field(..., description="Resource group name")
    azure_region: str = Field(default="westeurope", description="Azure region")

    # ── Azure AI Foundry project ──────────────────────────────────────────────
    foundry_project_endpoint: str = Field(..., description="Foundry project endpoint URL")

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    azure_openai_endpoint: str = Field(..., description="Azure OpenAI endpoint URL")
    azure_openai_api_key: SecretStr = Field(..., description="Azure OpenAI API key")
    azure_openai_api_version: str = Field(default="2024-10-21")

    chat_deployment_gpt4o: str = Field(default="gpt-4o")
    chat_deployment_gpt5: str = Field(default="gpt-5")
    embedding_deployment: str = Field(default="text-embedding-3-small")

    # ── Azure AI Search ───────────────────────────────────────────────────────
    search_endpoint: str = Field(..., description="Azure AI Search endpoint URL")
    search_admin_key: SecretStr = Field(..., description="Admin API key")
    search_index_patterns: str = Field(default="dv-patterns")
    search_index_decisions: str = Field(default="approved-decisions")

    # ── Observability ─────────────────────────────────────────────────────────
    appinsights_connection_string: SecretStr | None = Field(default=None)


@lru_cache(maxsize=1)
def get_settings() -> AISettings:
    """Return a cached :class:`AISettings` instance."""
    return AISettings()  # type: ignore[call-arg]
