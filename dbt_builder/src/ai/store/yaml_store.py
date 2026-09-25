"""AI-aware factory for the YAML metadata store.

Storage classes live in :mod:`dbt_builder.src.utils.yaml_store` (non-AI tier)
so Databricks notebook tasks can use them without crossing the AI boundary.
This module wires those classes to :class:`AISettings` and re-exports the
public surface the AI service facade depends on.

Usage::

    from dbt_builder.src.ai.store.yaml_store import make_yaml_store
    from dbt_builder.src.ai.settings import get_settings

    store = make_yaml_store(get_settings())
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dbt_builder.src.ai.store.executor import (
    has_databricks_creds,
    make_databricks_executor,
)
from dbt_builder.src.utils.yaml_store import (
    AdlsYamlStore,
    DeltaYamlStore,
    LocalYamlStore,
    YamlStore,
    catalog_from_yaml,
)

if TYPE_CHECKING:
    from dbt_builder.src.ai.settings import AISettings

_log = logging.getLogger(__name__)


def make_yaml_store(settings: AISettings) -> YamlStore:
    """Return the right :class:`YamlStore` based on ``AISettings``.

    Backend dispatch (``settings.metadata_store_backend``):

    * ``"delta"``                  → :class:`DeltaYamlStore` (Databricks UC).
    * ``"adls"``                   → :class:`AdlsYamlStore` (ADLS Gen2).
    * ``"local"``                  → :class:`LocalYamlStore`.
    * ``"auto"`` (default) chooses the first available in the order
      Delta → ADLS → Local based on which creds are present.
    """
    backend = (getattr(settings, "metadata_store_backend", "auto") or "auto").lower()

    if backend == "delta" or (backend == "auto" and has_databricks_creds(settings)):
        return _make_delta(settings)

    if backend == "adls" or (
        backend == "auto" and getattr(settings, "metadata_store_account", None)
    ):
        adls = _make_adls(settings)
        if adls is not None:
            return adls

    if backend not in {"auto", "local", "adls", "delta"}:
        raise ValueError(
            f"Unknown metadata_store_backend={backend!r}. Use one of: auto, local, adls, delta."
        )

    _log.debug("make_yaml_store: backend=%s → LocalYamlStore", backend)
    return LocalYamlStore()


def _make_delta(settings: AISettings) -> YamlStore:
    executor = make_databricks_executor(settings)
    return DeltaYamlStore(
        executor,
        catalog=settings.metadata_delta_catalog,
        schema=settings.metadata_delta_schema,
        table=settings.metadata_delta_yaml_table,
    )


def _make_adls(settings: AISettings) -> YamlStore | None:
    account: str | None = getattr(settings, "metadata_store_account", None)
    if not account:
        return None

    client_id: str | None = getattr(settings, "metadata_store_sp_client_id", None)
    client_secret_field = getattr(settings, "metadata_store_sp_client_secret", None)
    tenant_id: str | None = getattr(settings, "metadata_store_tenant_id", None)
    container: str = getattr(settings, "metadata_store_container", "dwa-metadata")

    if not all([client_id, client_secret_field, tenant_id]):
        _log.warning(
            "DWA_AI_METADATA_STORE_ACCOUNT is set but SP credentials are incomplete; "
            "falling back to LocalYamlStore."
        )
        return None

    client_secret: str = (
        client_secret_field.get_secret_value()
        if hasattr(client_secret_field, "get_secret_value")
        else str(client_secret_field)
    )

    return AdlsYamlStore(
        account_name=account,
        container=container,
        tenant_id=str(tenant_id),
        client_id=str(client_id),
        client_secret=client_secret,
    )


__all__ = [
    "AdlsYamlStore",
    "DeltaYamlStore",
    "LocalYamlStore",
    "YamlStore",
    "catalog_from_yaml",
    "make_yaml_store",
]
