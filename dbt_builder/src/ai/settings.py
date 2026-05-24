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

    # Primary chat deployment used by Phase 2 modelling agents. Defaults to
    # gpt-5 for stronger structured-reasoning quality on schema -> DV2 mapping;
    # set to ``gpt-4o`` for lower-latency, deterministic (temperature=0) runs.
    primary_chat_deployment: str = Field(default="gpt-5")

    # ── Modelling-agent token budgets ─────────────────────────────────────────
    # Per-deployment cap on completion tokens. gpt-5 spends a non-trivial share
    # of the budget on invisible reasoning tokens before emitting any visible
    # content, so larger payloads (many tables / columns) need a higher cap to
    # leave room for the JSON answer. Non-reasoning models are fine with the
    # default. Both are env-overridable so ops can raise the cap without code
    # changes when a future source system needs more headroom.
    modeller_max_tokens_default: int = Field(default=4096)
    modeller_max_tokens_gpt5: int = Field(default=16384)

    # ── Vector backend (Phase 2) ──────────────────────────────────────────────
    # 'faiss' is the default for offline / dev work and unit tests; 'azure'
    # uses Azure AI Search (any SKU) when ``search_endpoint`` is configured.
    vector_backend: str = Field(default="faiss")
    vector_cache_dir: str = Field(
        default=".cache/ai",
        description="Directory for FAISS index files and embedding cache (gitignored).",
    )

    # ── Azure AI Search (optional in Phase 0/1; required from Phase 2 onward) ─
    search_endpoint: str | None = Field(default=None, description="Azure AI Search endpoint URL")
    search_admin_key: SecretStr | None = Field(default=None, description="Admin API key")
    search_index_patterns: str = Field(default="dv-patterns")
    search_index_decisions: str = Field(default="approved-decisions")

    # ── YAML Metadata store (ADLS Gen2) ──────────────────────────────────────
    # Set DWA_AI_METADATA_STORE_ACCOUNT to enable ADLS Gen2-backed storage.
    # When unset the service falls back to LocalYamlStore (.cache/approved_yamls/).
    metadata_store_account: str | None = Field(
        default=None,
        description=(
            "ADLS Gen2 storage account name (without .dfs.core.windows.net). "
            "Leave blank to use the local filesystem store in dev/CI."
        ),
    )
    metadata_store_container: str = Field(
        default="dwa-metadata",
        description="Container / filesystem name within the storage account.",
    )
    metadata_store_sp_client_id: str | None = Field(
        default=None,
        description="Service principal client ID for ADLS Gen2 read/write access.",
    )
    metadata_store_sp_client_secret: SecretStr | None = Field(
        default=None,
        description="Service principal client secret for ADLS Gen2 read/write access.",
    )
    metadata_store_tenant_id: str | None = Field(
        default=None,
        description="Azure AD tenant ID for the ADLS Gen2 service principal.",
    )

    # ── Observability ─────────────────────────────────────────────────────────
    appinsights_connection_string: SecretStr | None = Field(default=None)

    def modeller_max_tokens_for(self, deployment: str) -> int:
        """Return the modelling-agent token budget for ``deployment``.

        gpt-5-family deployments use ``modeller_max_tokens_gpt5`` (default
        16384) to absorb the invisible reasoning-token overhead; everything
        else uses ``modeller_max_tokens_default`` (default 4096).
        """
        if deployment.startswith("gpt-5"):
            return self.modeller_max_tokens_gpt5
        return self.modeller_max_tokens_default


@lru_cache(maxsize=1)
def get_settings() -> AISettings:
    """Return a cached :class:`AISettings` instance."""
    return AISettings()  # type: ignore[call-arg]
