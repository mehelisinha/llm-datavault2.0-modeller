"""API runtime settings — loaded from environment (no hardcoded deployment values)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from dbt_builder.api.stub_catalog import (
    DEFAULT_METADATA_DIR,
    DEFAULT_VAULT_SCHEMAS,
    discover_stub_catalog_map,
)


class ApiSettings(BaseSettings):
    """Configuration for the FastAPI surface and discovery providers."""

    model_config = SettingsConfigDict(
        env_prefix="DWA_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discovery_mode: Literal["stub", "spark", "databricks"] = Field(
        default="stub",
        description=(
            "stub: in-memory fixtures (no external deps); "
            "spark: Databricks SQL via get_spark() (needs PySpark/Databricks Connect); "
            "databricks: Unity Catalog REST API via databricks-sdk (no cluster)."
        ),
    )
    stub_catalog_map_json: str = Field(
        default="",
        description=(
            "Optional JSON override mapping catalog -> schemas (stub mode). "
            "When empty, the map is auto-discovered from `stub_metadata_dir`."
        ),
    )
    stub_metadata_dir: str | None = Field(
        default=None,
        description=(
            "Directory scanned for *.yaml/*.yml files to derive the stub "
            "catalog map. Defaults to `<repo>/poc/metadata`."
        ),
    )
    stub_default_vault_schemas: str = Field(
        default=",".join(DEFAULT_VAULT_SCHEMAS),
        description=(
            "Comma-separated schema names appended to every auto-discovered "
            "catalog so the UI can offer a vault-schema choice."
        ),
    )
    default_system_id: str = Field(default="iec_cim")
    default_system_name: str = Field(default="IEC CIM")
    default_record_source: str = Field(default="iec_cim")

    # ── Databricks Unity Catalog REST (discovery_mode="databricks") ──────────
    # The SDK also resolves these from the conventional DATABRICKS_HOST /
    # DATABRICKS_TOKEN env vars when our prefixed forms are unset; we accept
    # both so users can keep a single Databricks login working for both this
    # API and the dbt CLI / Databricks Connect tooling.
    databricks_host: str | None = Field(
        default=None,
        description=(
            "Workspace URL, e.g. https://redacted-host.example.net. "
            "Falls back to env DATABRICKS_HOST when unset."
        ),
    )
    databricks_token: str | None = Field(
        default=None,
        description=(
            "Personal Access Token. Optional — leave blank to use the auth "
            "method selected by `databricks_auth_type` (e.g. Azure CLI OAuth)."
        ),
    )
    databricks_auth_type: str | None = Field(
        default=None,
        description=(
            "Databricks SDK auth_type. Common values: 'pat', 'azure-cli', "
            "'databricks-cli', 'azure-msi'. When unset, the SDK picks "
            "automatically based on which credentials it can find."
        ),
    )

    aad_tenant_id: str | None = Field(default=None)
    aad_api_client_id: str | None = Field(
        default=None,
        description="Application (client) ID of the protected API — JWT audience.",
    )
    aad_admin_app_role: str = Field(
        default="Admin",
        description=(
            "App role value (case-insensitive) that grants admin privileges. "
            "Must match the 'value' field of the role on the API app registration."
        ),
    )
    admin_emails: str = Field(
        default="",
        description=(
            "Comma-separated email/UPN allowlist used as an admin fallback when "
            "the bearer token carries no 'roles' claim (e.g. during early rollout "
            "before app roles are assigned). Also honoured in dev (X-Actor) mode."
        ),
    )
    cors_allowed_origins: str = Field(
        default="",
        description=(
            "Comma-separated list of origins allowed by CORS (e.g. "
            "'http://localhost:5173,https://dwa.eon.com'). Empty disables CORS "
            "— safe default for same-origin production deployments."
        ),
    )

    # ── Hide DWA's own metadata Delta tables from UI discovery dropdowns. ──
    # Read directly from the publisher-side env vars (DWA_AI_METADATA_DELTA_*)
    # so the catalog/schema name is configured ONCE and stays in sync.
    metadata_delta_catalog: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "DWA_API_METADATA_DELTA_CATALOG",
            "DWA_AI_METADATA_DELTA_CATALOG",
        ),
        description="Catalog hosting the DWA metadata Delta tables (hidden from discovery).",
    )
    metadata_delta_schema: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "DWA_API_METADATA_DELTA_SCHEMA",
            "DWA_AI_METADATA_DELTA_SCHEMA",
        ),
        description="Schema hosting the DWA metadata Delta tables (hidden from discovery).",
    )
    hide_metadata_from_discovery: bool = Field(
        default=True,
        description=(
            "When True (default), filter the configured metadata catalog/schema "
            "out of /api/discovery/* responses so users cannot accidentally point "
            "vault generation at DWA's own audit tables."
        ),
    )

    ui_dist_path: str | None = Field(
        default=None,
        description="Override path to built React assets; auto-detected when unset.",
    )

    @field_validator("stub_catalog_map_json")
    @classmethod
    def _validate_catalog_map_json(cls, value: str) -> str:
        # Empty string means "auto-discover from metadata_dir"; only parse when set.
        if not value.strip():
            return ""
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("stub_catalog_map_json must be a JSON object")
        for key, schemas in parsed.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("catalog keys must be non-empty strings")
            if not isinstance(schemas, list) or not all(isinstance(s, str) for s in schemas):
                raise ValueError(f"schemas for '{key}' must be a list of strings")
        return value

    @property
    def metadata_dir(self) -> Path:
        """Effective metadata directory used to derive stub catalogs."""
        return Path(self.stub_metadata_dir) if self.stub_metadata_dir else DEFAULT_METADATA_DIR

    @property
    def default_vault_schemas(self) -> tuple[str, ...]:
        """Parsed tuple form of :attr:`stub_default_vault_schemas`."""
        return tuple(s.strip() for s in self.stub_default_vault_schemas.split(",") if s.strip())

    @property
    def stub_catalog_map(self) -> dict[str, list[str]]:
        """Catalog -> schemas map for stub mode.

        Explicit JSON override (``DWA_API_STUB_CATALOG_MAP_JSON``) wins;
        otherwise the map is derived from YAMLs in :attr:`metadata_dir`.
        """
        if self.stub_catalog_map_json:
            return json.loads(self.stub_catalog_map_json)
        return discover_stub_catalog_map(
            self.metadata_dir,
            default_vault_schemas=self.default_vault_schemas,
        )

    @property
    def auth_enabled(self) -> bool:
        return bool(self.aad_tenant_id and self.aad_api_client_id)

    @property
    def aad_issuer(self) -> str | None:
        if not self.aad_tenant_id:
            return None
        return f"https://login.microsoftonline.com/{self.aad_tenant_id}/v2.0"

    @property
    def aad_jwks_uri(self) -> str | None:
        if not self.aad_tenant_id:
            return None
        return f"https://login.microsoftonline.com/{self.aad_tenant_id}/discovery/v2.0/keys"

    @property
    def admin_email_set(self) -> frozenset[str]:
        """Lower-cased allowlist of admin emails (empty when unset)."""
        return frozenset(
            e.strip().lower() for e in self.admin_emails.split(",") if e.strip()
        )

    @property
    def cors_origin_list(self) -> list[str]:
        """Parsed CORS origins (empty list disables CORS)."""
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
