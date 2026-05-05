"""Live discovery from a Spark / Databricks catalogue.

Wraps the existing Spark integration and produces the same
:class:`~dbt_builder.src.ai.contracts.payloads.DiscoveryPayload` that
:func:`schema_discovery.discover_from_yaml` produces, so downstream agents do
not care about the source.

Why a separate module:

* Importing PySpark at package import time would force every offline test to
  install Spark. We lazy-import inside :func:`discover_from_spark` instead.
* The adapter accepts an injected ``spark`` session (or any object exposing a
  ``sql(query) -> DataFrame``-like API), so unit tests can pass a stub.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from dbt_builder.src.ai.contracts.payloads import (
    DiscoveryPayload,
    SourceColumn,
    SourceSystem,
    SourceTable,
)
from dbt_builder.src.ai.discovery.schema_discovery import (
    DEFAULT_SOURCE_TYPE,
    build_source_column,
)


class _RowLike(Protocol):
    """Minimal protocol for rows returned by ``spark.sql(...).collect()``."""

    def asDict(self) -> dict[str, Any]: ...  # noqa: N802 (Spark API)


class _DataFrameLike(Protocol):
    def collect(self) -> Iterable[_RowLike]: ...


class _SparkLike(Protocol):
    def sql(self, query: str) -> _DataFrameLike: ...


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Best-effort conversion of a Spark Row (or stub) to a plain dict."""
    if hasattr(row, "asDict"):
        return dict(row.asDict())
    if isinstance(row, dict):
        return dict(row)
    raise TypeError(f"Unsupported row type: {type(row)!r}")


def _list_tables(spark: _SparkLike, catalog: str, schema: str) -> tuple[str, ...]:
    rows = spark.sql(f"SHOW TABLES IN `{catalog}`.`{schema}`").collect()
    names: list[str] = []
    for row in rows:
        d = _row_to_dict(row)
        # Spark's SHOW TABLES uses `tableName`; some catalogs return `name`.
        name = d.get("tableName") or d.get("name")
        is_temp = d.get("isTemporary", False) or d.get("is_temporary", False)
        if name and not is_temp:
            names.append(str(name))
    return tuple(names)


def _describe_columns(
    spark: _SparkLike, catalog: str, schema: str, table: str
) -> tuple[SourceColumn, ...]:
    rows = spark.sql(f"DESCRIBE TABLE `{catalog}`.`{schema}`.`{table}`").collect()
    columns: list[SourceColumn] = []
    ordinal = 0
    for row in rows:
        d = _row_to_dict(row)
        name = d.get("col_name")
        # DESCRIBE TABLE appends a blank row and a "# Partition Information"
        # block at the end; both are skipped here.
        if not name or str(name).startswith("#") or str(name).strip() == "":
            break
        raw_dtype = str(d.get("data_type", "")).strip() or "string"
        comment = d.get("comment")
        # DESCRIBE TABLE doesn't expose nullability; default to True (Spark
        # treats most columns as nullable). Callers needing exact nullability
        # can post-process via INFORMATION_SCHEMA.
        columns.append(
            build_source_column(
                name=str(name),
                raw_dtype=raw_dtype,
                nullable=True,
                description=str(comment) if comment else None,
                ordinal=ordinal,
            )
        )
        ordinal += 1
    return tuple(columns)


def discover_from_spark(
    spark: _SparkLike,
    *,
    catalog: str,
    schema: str,
    system_id: str,
    system_name: str,
    record_source: str | None = None,
    tables: Iterable[str] | None = None,
) -> DiscoveryPayload:
    """Enumerate ``catalog.schema`` and return a :class:`DiscoveryPayload`.

    Parameters
    ----------
    spark
        A SparkSession or any object with a ``sql(query)`` method whose result
        supports ``.collect()`` returning rows with ``asDict()``. Tests pass a
        stub; production code passes ``shared.utils.spark.get_spark()``.
    catalog, schema
        The Unity Catalog (or Hive metastore) location to enumerate.
    system_id, system_name
        Identity stamped on the resulting :class:`SourceSystem`. Required so
        downstream RECORD_SOURCE values are stable across runs.
    record_source
        Optional explicit RECORD_SOURCE override. Defaults to
        ``f"{catalog}.{schema}"`` when omitted.
    tables
        Optional whitelist of table names. When provided, only these tables
        are described; ``SHOW TABLES`` is skipped entirely.
    """
    if tables is None:
        names = _list_tables(spark, catalog, schema)
    else:
        names = tuple(t for t in tables if t)

    source_tables: list[SourceTable] = []
    for name in names:
        cols = _describe_columns(spark, catalog, schema, name)
        # Drop tables Spark refuses to describe (empty result) rather than
        # emit a hollow entry the modeller would have to filter out.
        if not cols:
            continue
        source_tables.append(
            SourceTable(
                name=name,
                schema_name=schema,
                catalog=catalog,
                columns=cols,
            )
        )

    system = SourceSystem(
        system_id=system_id,
        system_name=system_name,
        source_type=DEFAULT_SOURCE_TYPE,
        catalog=catalog,
        schema_name=schema,
        record_source=record_source or f"{catalog}.{schema}",
    )
    return DiscoveryPayload(system=system, tables=tuple(source_tables))


__all__ = ["discover_from_spark"]
