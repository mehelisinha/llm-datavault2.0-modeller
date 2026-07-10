"""Thin wrapper around ``databricks-sql-connector``.

A single helper used by every Delta-backed store (YAML versions, approval
audit trail). Centralising the connect / execute / fetch dance avoids
duplicating connection management in each store class and keeps the
``databricks.sql`` import truly lazy.
"""

from __future__ import annotations

import re
import threading
from typing import Any, Callable, Sequence

# Unity Catalog identifiers that we interpolate directly into SQL (they are
# config-time constants, never runtime/user input). Validated against this
# whitelist so a typo can never turn into SQL injection.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(ident: str) -> str:
    """Return ``ident`` if it is a safe SQL identifier, else raise ``ValueError``."""
    if not _IDENT_RE.match(ident):
        raise ValueError(f"Invalid Delta identifier: {ident!r}")
    return ident


def quote_fqn(catalog: str, schema: str, table: str) -> str:
    """Validate the three parts and return the backtick-quoted 3-level name.

    e.g. ``quote_fqn("cat", "sch", "tbl")`` -> ``cat``.``sch``.``tbl`` with each
    identifier wrapped in backticks so reserved words / mixed case are safe.
    """
    for ident in (catalog, schema, table):
        validate_identifier(ident)
    return f"`{catalog}`.`{schema}`.`{table}`"


class DatabricksSqlExecutor:
    """Lazy, lock-serialised wrapper for a Databricks SQL warehouse connection.

    Each store instance owns one executor. The connector itself is not
    thread-safe for parallel statements on the same connection, so a
    per-instance ``threading.Lock`` serialises writes/reads. For high
    concurrency, instantiate more stores (one per worker) — connections
    are cheap and the connector pools internally on the warehouse side.
    """

    def __init__(
        self,
        *,
        server_hostname: str,
        http_path: str,
        access_token: str | None = None,
        credentials_provider: Callable[[], Callable[[], dict[str, str]]] | None = None,
    ) -> None:
        if not server_hostname or not http_path:
            raise ValueError("DatabricksSqlExecutor requires server_hostname and http_path.")
        # Exactly one auth mechanism must be supplied: a static PAT (access_token)
        # or an Azure AD credentials_provider. The provider is preferred when both
        # are set so an Entra-only workspace never falls back to a rejected PAT.
        if not access_token and credentials_provider is None:
            raise ValueError(
                "DatabricksSqlExecutor requires either access_token (PAT) or "
                "credentials_provider (Azure AD)."
            )
        self._server_hostname = server_hostname
        self._http_path = http_path
        self._access_token = access_token
        self._credentials_provider = credentials_provider
        self._lock = threading.Lock()
        self._conn: Any | None = None

    def _ensure_conn(self) -> Any:
        if self._conn is None:
            from databricks import sql as _dbx_sql  # noqa: PLC0415 — lazy import

            connect_kwargs: dict[str, Any] = {
                "server_hostname": self._server_hostname,
                "http_path": self._http_path,
            }
            if self._credentials_provider is not None:
                connect_kwargs["credentials_provider"] = self._credentials_provider
            else:
                connect_kwargs["access_token"] = self._access_token
            self._conn = _dbx_sql.connect(**connect_kwargs)
        return self._conn

    def execute(self, statement: str, params: Sequence[Any] | None = None) -> None:
        with self._lock:
            conn = self._ensure_conn()
            cursor = conn.cursor()
            try:
                cursor.execute(statement, params or ())
            finally:
                cursor.close()

    def fetchall(
        self, statement: str, params: Sequence[Any] | None = None
    ) -> list[tuple[Any, ...]]:
        with self._lock:
            conn = self._ensure_conn()
            cursor = conn.cursor()
            try:
                cursor.execute(statement, params or ())
                return [tuple(row) for row in cursor.fetchall()]
            finally:
                cursor.close()

    def fetchone(
        self, statement: str, params: Sequence[Any] | None = None
    ) -> tuple[Any, ...] | None:
        with self._lock:
            conn = self._ensure_conn()
            cursor = conn.cursor()
            try:
                cursor.execute(statement, params or ())
                row = cursor.fetchone()
                return tuple(row) if row is not None else None
            finally:
                cursor.close()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None


# Well-known Azure application ID for the Azure Databricks login app. The AAD
# access-token scope for ANY Azure Databricks workspace is this app's
# ``/.default``; azure-identity exchanges the local az-login / managed-identity
# session for a workspace-scoped token against it.
_AZURE_DATABRICKS_LOGIN_APP_ID = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"
_AZURE_DATABRICKS_SCOPE = f"{_AZURE_DATABRICKS_LOGIN_APP_ID}/.default"

# auth_type values that select Azure AD (Entra) auth instead of a static PAT.
AAD_AUTH_TYPES = frozenset({"azure-cli", "aad", "azure", "azure-ad", "oauth"})


def azure_ad_credentials_provider(
    *, auth_type: str = "azure-cli"
) -> Callable[[], Callable[[], dict[str, str]]]:
    """Return a databricks-sql ``credentials_provider`` backed by azure-identity.

    The connector calls the returned provider once to obtain a *header factory*,
    then calls that factory on every request (see ``ExternalAuthProvider`` in the
    connector). Fetching the token inside the factory means azure-identity's own
    cache refreshes it transparently, so a long-lived connection never sends an
    expired token.

    ``auth_type="azure-cli"`` uses the local ``az login`` session
    (:class:`AzureCliCredential`); any other AAD value falls back to
    :class:`DefaultAzureCredential` (env vars, managed identity, az login, ...).
    """

    def _provider() -> Callable[[], dict[str, str]]:
        from azure.identity import (  # noqa: PLC0415 — lazy, optional [ai] dep
            AzureCliCredential,
            DefaultAzureCredential,
        )

        credential = AzureCliCredential() if auth_type == "azure-cli" else DefaultAzureCredential()

        def _header_factory() -> dict[str, str]:
            token = credential.get_token(_AZURE_DATABRICKS_SCOPE).token
            return {"Authorization": f"Bearer {token}"}

        return _header_factory

    return _provider


def ensure_schema(executor: DatabricksSqlExecutor, *, catalog: str, schema: str) -> None:
    """Idempotently create ``{catalog}.{schema}`` so first deploy is zero-touch.

    The Delta stores only ``CREATE TABLE IF NOT EXISTS``; that fails when the
    target schema does not exist yet. Callers with ``CREATE SCHEMA`` rights run
    this once at store construction. A principal lacking the grant will get a
    permission error here — surfaced loudly rather than as a confusing
    "table not found" later.
    """
    validate_identifier(catalog)
    validate_identifier(schema)
    executor.execute(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")


__all__ = [
    "AAD_AUTH_TYPES",
    "DatabricksSqlExecutor",
    "azure_ad_credentials_provider",
    "ensure_schema",
    "quote_fqn",
    "validate_identifier",
]
