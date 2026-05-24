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

from dbt_builder.src.utils.yaml_store import (
    AdlsYamlStore,
    LocalYamlStore,
    YamlStore,
    catalog_from_yaml,
)

if TYPE_CHECKING:
    from dbt_builder.src.ai.settings import AISettings

_log = logging.getLogger(__name__)


def make_yaml_store(settings: AISettings) -> YamlStore:
    """Return the right :class:`YamlStore` based on ``AISettings``.

    Decision logic:

    1. If ``DWA_AI_METADATA_STORE_ACCOUNT`` is set **and** SP credentials
       are present → :class:`AdlsYamlStore` (production).
    2. Otherwise → :class:`LocalYamlStore` (dev fallback, no Azure deps).
    """
    account: str | None = getattr(settings, "metadata_store_account", None)
    if not account:
        _log.debug("make_yaml_store: no ADLS account configured → LocalYamlStore")
        return LocalYamlStore()

    client_id: str | None = getattr(settings, "metadata_store_sp_client_id", None)
    client_secret_field = getattr(settings, "metadata_store_sp_client_secret", None)
    tenant_id: str | None = getattr(settings, "metadata_store_tenant_id", None)
    container: str = getattr(settings, "metadata_store_container", "dwa-metadata")

    if not all([client_id, client_secret_field, tenant_id]):
        _log.warning(
            "DWA_AI_METADATA_STORE_ACCOUNT is set but SP credentials are incomplete; "
            "falling back to LocalYamlStore."
        )
        return LocalYamlStore()

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
    "LocalYamlStore",
    "YamlStore",
    "catalog_from_yaml",
    "make_yaml_store",
]
