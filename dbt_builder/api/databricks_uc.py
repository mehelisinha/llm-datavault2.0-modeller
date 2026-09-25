"""Unity Catalog REST adapter for the discovery API (mode = "databricks").

This module exposes a thin, dependency-light wrapper over the Databricks SDK's
``WorkspaceClient`` so the discovery router can list catalogs/schemas/tables
and build snapshot callables **without spinning up Spark or a cluster**.

Why this exists
---------------
The router historically supported two modes:

* ``stub``   — reads YAMLs from ``poc/metadata/`` (offline / CI / no secrets)
* ``spark``  — runs ``SHOW CATALOGS`` etc. through ``get_spark()``, which
  locally requires Databricks Connect attached to a running cluster.

For a developer who just wants the UI dropdowns to reflect *all* catalogs in
their workspace, booting a Spark plan for every dropdown click is overkill.
The Unity Catalog REST endpoints answer the same questions in milliseconds and
respect the caller's UC ACLs — exactly what Databricks' own Catalog Explorer
does.

Auth strategy
-------------
Auth is delegated to the SDK. We construct ``WorkspaceClient`` with whichever
of ``host``, ``token``, ``auth_type`` the caller supplied via :class:`ApiSettings`
and let the SDK's resolution chain do the rest. The two common paths:

* PAT — set ``DWA_API_DATABRICKS_TOKEN`` (or ``DATABRICKS_TOKEN``).
* Azure CLI OAuth — set ``DWA_API_DATABRICKS_AUTH_TYPE=azure-cli`` and have an
  active ``az login`` session.

Caching
-------
The ``WorkspaceClient`` instance is cached per ``(host, token, auth_type)``
triple via :func:`get_workspace_client` so we don't re-authenticate on every
HTTP request. Cache is bounded to a single live client in practice because
the settings object is itself ``lru_cache``'d.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover — typing only; SDK is a runtime dep
    from databricks.sdk import WorkspaceClient

from dbt_builder.api.settings import ApiSettings


def _import_workspace_client() -> type[WorkspaceClient]:
    """Import ``WorkspaceClient`` lazily so stub-mode users don't need the SDK."""
    try:
        from databricks.sdk import WorkspaceClient  # noqa: PLC0415 — lazy import
    except ImportError as exc:  # pragma: no cover — covered by integration env
        raise RuntimeError(
            "discovery_mode='databricks' requires the 'databricks-sdk' package. "
            "Install it via `pip install databricks-sdk` or set "
            "DWA_API_DISCOVERY_MODE=stub for offline development."
        ) from exc
    return WorkspaceClient


@lru_cache(maxsize=8)
def _build_client(
    host: str | None,
    token: str | None,
    auth_type: str | None,
) -> WorkspaceClient:
    """Construct a ``WorkspaceClient`` keyed by its credential triple.

    The cache key must be hashable, so we accept the three primitives rather
    than the :class:`ApiSettings` instance (which is intentionally mutable).
    """
    WorkspaceClient = _import_workspace_client()
    kwargs: dict[str, Any] = {}
    if host:
        kwargs["host"] = host
    if token:
        kwargs["token"] = token
    if auth_type:
        kwargs["auth_type"] = auth_type
    return WorkspaceClient(**kwargs)


def get_workspace_client(settings: ApiSettings) -> WorkspaceClient:
    """Return a cached ``WorkspaceClient`` for the active :class:`ApiSettings`."""
    return _build_client(
        host=settings.databricks_host,
        token=settings.databricks_token,
        auth_type=settings.databricks_auth_type,
    )


def reset_client_cache() -> None:
    """Drop cached clients — used by tests that mutate auth env vars."""
    _build_client.cache_clear()


# ---------------------------------------------------------------------------
# Listings — used by the three GET endpoints
# ---------------------------------------------------------------------------


def list_catalogs(client: WorkspaceClient) -> tuple[str, ...]:
    """Return every catalog name the caller can ``USE CATALOG`` on, sorted."""
    return tuple(sorted(c.name for c in client.catalogs.list() if c.name))


def list_schemas(client: WorkspaceClient, catalog: str) -> tuple[str, ...]:
    """Return every schema under ``catalog`` visible to the caller, sorted."""
    return tuple(sorted(s.name for s in client.schemas.list(catalog_name=catalog) if s.name))


def list_tables(
    client: WorkspaceClient,
    catalog: str,
    schema: str,
) -> tuple[str, ...]:
    """Return every table name under ``catalog.schema`` visible to the caller, sorted."""
    return tuple(
        sorted(
            t.name for t in client.tables.list(catalog_name=catalog, schema_name=schema) if t.name
        )
    )


# ---------------------------------------------------------------------------
# Snapshot callables — mirror the spark / stub adapters
# ---------------------------------------------------------------------------

# Aliases match the callable shapes the service layer expects.
_ListEntities = Callable[[str, str], list[tuple[str, str]]]
_DescribeVault = Callable[[str, str, str], list[tuple[str, str, bool, str | None]]]
_ListTables = Callable[[str, str], list[str]]
_DescribeBronze = Callable[[str, str, str], list[tuple[str, str, bool, str | None, bool]]]


def _coerce_table_type(table_type: Any) -> str:
    """Render the SDK's ``TableType`` enum as a plain string ("TABLE" fallback)."""
    if table_type is None:
        return "TABLE"
    value = getattr(table_type, "value", None)
    return str(value) if value is not None else str(table_type)


def _table_full_name(catalog: str, schema: str, table: str) -> str:
    return f"{catalog}.{schema}.{table}"


def make_snapshot_callables(
    client: WorkspaceClient,
    catalog: str,
    vault_schema: str,
    bronze_schema: str,
) -> tuple[_ListEntities, _DescribeVault, _ListTables, _DescribeBronze]:
    """Build the four callables ``DwaService.inspect_catalog`` / ``read_bronze`` expect.

    The returned closures hit the UC REST endpoints lazily — ``list_*`` is
    called once per schema, ``describe_*`` once per filtered table — which
    keeps the snapshot cost proportional to the size of the *filtered* table
    set rather than the whole schema.
    """

    def list_vault_entities(_cat: str, schema_name: str) -> list[tuple[str, str]]:
        return [
            (t.name, _coerce_table_type(t.table_type))
            for t in client.tables.list(catalog_name=catalog, schema_name=schema_name)
            if t.name
        ]

    def describe_vault(
        _cat: str, schema_name: str, table: str
    ) -> list[tuple[str, str, bool, str | None]]:
        info = client.tables.get(full_name=_table_full_name(catalog, schema_name, table))
        return [
            (
                col.name,
                col.type_text or "string",
                bool(col.nullable) if col.nullable is not None else True,
                col.comment,
            )
            for col in (info.columns or [])
            if col.name
        ]

    def list_bronze_tables(_cat: str, schema_name: str) -> list[str]:
        return [
            t.name
            for t in client.tables.list(catalog_name=catalog, schema_name=schema_name)
            if t.name
        ]

    def describe_bronze(
        _cat: str, schema_name: str, table: str
    ) -> list[tuple[str, str, bool, str | None, bool]]:
        info = client.tables.get(full_name=_table_full_name(catalog, schema_name, table))
        return [
            (
                col.name,
                col.type_text or "string",
                bool(col.nullable) if col.nullable is not None else True,
                col.comment,
                col.partition_index is not None,
            )
            for col in (info.columns or [])
            if col.name
        ]

    # Reference vault_schema / bronze_schema so the caller can see they're part
    # of the closure's contract (each callable receives the schema at call
    # time, so we don't pin them here — this comment keeps the API explicit).
    _ = vault_schema, bronze_schema

    return list_vault_entities, describe_vault, list_bronze_tables, describe_bronze
