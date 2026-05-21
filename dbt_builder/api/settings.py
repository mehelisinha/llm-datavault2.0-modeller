"""API runtime settings — loaded from environment (no hardcoded deployment values)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
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

    discovery_mode: Literal["stub", "spark"] = Field(
        default="stub",
        description="stub: in-memory fixtures; spark: Databricks SQL via get_spark().",
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

    aad_tenant_id: str | None = Field(default=None)
    aad_api_client_id: str | None = Field(
        default=None,
        description="Application (client) ID of the protected API — JWT audience.",
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


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
