"""AI-aware factory for the approval audit store.

Mirrors :mod:`dbt_builder.src.ai.store.yaml_store`'s ``make_yaml_store``
factory — keeps store backend selection in ONE place so the service facade
stays implementation-agnostic.

Backend selection (driven by :class:`AISettings.metadata_store_backend`):

* ``"delta"``  → :class:`DeltaApprovalStore` (Databricks Unity Catalog).
* ``"local"`` / ``"adls"`` / ``"auto"`` (no Databricks creds) → :class:`SqliteApprovalStore`.

ADLS Gen2 has no approval store of its own — the audit trail belongs in
Delta (queryable) or SQLite (dev). When the user picks the ``"adls"`` YAML
backend on a non-Databricks workstation, the approval store stays on SQLite.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from dbt_builder.src.ai.store import (
    ApprovalStore,
    DeltaApprovalStore,
    SqliteApprovalStore,
)

if TYPE_CHECKING:
    from dbt_builder.src.ai.settings import AISettings

_log = logging.getLogger(__name__)


def make_approval_store(settings: AISettings) -> ApprovalStore:
    """Return the right :class:`ApprovalStore` based on ``AISettings``."""
    backend = (getattr(settings, "metadata_store_backend", "auto") or "auto").lower()
    has_dbx = _has_databricks_creds(settings)

    if backend == "delta" or (backend == "auto" and has_dbx):
        if not has_dbx:
            raise RuntimeError(
                "metadata_store_backend='delta' requires databricks_workspace_url, "
                "databricks_http_path and databricks_token to be set."
            )
        from dbt_builder.src.utils.databricks_sql import DatabricksSqlExecutor

        token = settings.databricks_token  # type: ignore[union-attr]
        token_value = token.get_secret_value() if hasattr(token, "get_secret_value") else str(token)
        executor = DatabricksSqlExecutor(
            server_hostname=str(settings.databricks_workspace_url),
            http_path=str(settings.databricks_http_path),
            access_token=token_value,
        )
        return DeltaApprovalStore(
            executor,
            catalog=settings.metadata_delta_catalog,
            schema=settings.metadata_delta_schema,
            table=settings.metadata_delta_approvals_table,
        )

    _log.debug("make_approval_store: backend=%s → SqliteApprovalStore", backend)
    return SqliteApprovalStore(Path(".cache") / "approvals.sqlite")


def _has_databricks_creds(settings: AISettings) -> bool:
    return all(
        bool(getattr(settings, name, None))
        for name in ("databricks_workspace_url", "databricks_http_path", "databricks_token")
    )


__all__ = [
    "ApprovalStore",
    "DeltaApprovalStore",
    "SqliteApprovalStore",
    "make_approval_store",
]
