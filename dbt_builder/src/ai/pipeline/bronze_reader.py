"""Step 2 — Bronze Schema Reader.

Lists bronze tables matching include / exclude patterns and runs
``DESCRIBE TABLE`` on each to capture columns, dtypes and partitioning. Also
performs the lightweight business-key sanity check called for in the pptx:
each table should expose a recognisable BK column (``mrid``, ``*_id``,
``*_key``, ``*_mrid``); tables that don't are listed in
``BronzeSnapshot.missing_business_keys`` so the UI Step 2 can badge them.

Like the catalog inspector this module is Spark-free at import time; callers
inject ``ListTables`` and ``DescribeTable`` callables.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from datetime import datetime, timezone

from dbt_builder.src.ai.contracts.catalog import (
    BronzeColumn,
    BronzeSnapshot,
    BronzeTable,
)

ListTables = Callable[[str, str], Iterable[str]]
"""Signature: ``(catalog, schema) -> iterable of table names``."""

DescribeTable = Callable[
    [str, str, str],
    Iterable[tuple[str, str, bool, str | None, bool]],
]
"""Signature: ``(catalog, schema, table) -> iterable of
(name, dtype, nullable, comment, is_partition)``."""


_BK_EXACT = frozenset({"mrid", "id", "uuid"})
_BK_SUFFIXES = ("_mrid", "_id", "_key", "_uuid")


def _detect_business_key(columns: Iterable[BronzeColumn]) -> str | None:
    """Return the first plausible business-key column name (case-insensitive).

    Heuristic, mirroring the agent.md rules:

    * Prefer exact matches against ``mrid`` / ``id`` / ``uuid``.
    * Fall back to columns ending in ``_mrid`` / ``_id`` / ``_key`` / ``_uuid``,
      excluding obvious foreign keys (the diff/architect steps disambiguate
      true BKs from FKs by counting cross-table references).
    """
    cols = list(columns)
    for col in cols:
        if col.name.lower() in _BK_EXACT:
            return col.name
    for col in cols:
        lower = col.name.lower()
        if any(lower.endswith(suffix) for suffix in _BK_SUFFIXES):
            return col.name
    return None


def _matches_any(name: str, patterns: tuple[str, ...]) -> bool:
    return any(re.fullmatch(p, name, flags=re.IGNORECASE) for p in patterns)


def read_bronze(
    *,
    catalog: str,
    schema_name: str,
    list_tables: ListTables,
    describe_table: DescribeTable,
    include_patterns: tuple[str, ...] = (),
    exclude_patterns: tuple[str, ...] = (),
) -> BronzeSnapshot:
    """Build a :class:`BronzeSnapshot` for ``catalog.schema_name``.

    ``include_patterns`` / ``exclude_patterns`` are full-match regexes
    (case-insensitive). Empty include = include everything; exclude wins on
    conflict. Defaults exclude common temp / staging suffixes are NOT applied
    here — pass them explicitly so the choice is auditable per environment.
    """
    tables: list[BronzeTable] = []
    missing_bks: list[str] = []

    for table_name in list_tables(catalog, schema_name):
        if include_patterns and not _matches_any(table_name, include_patterns):
            continue
        if exclude_patterns and _matches_any(table_name, exclude_patterns):
            continue

        cols = tuple(
            BronzeColumn(
                name=col_name,
                raw_dtype=raw_dtype,
                nullable=nullable,
                comment=comment,
                is_partition=is_partition,
            )
            for col_name, raw_dtype, nullable, comment, is_partition in describe_table(
                catalog, schema_name, table_name
            )
        )
        if not cols:
            # An empty column list would fail BronzeTable validation; record
            # the table as a missing-BK warning instead so the UI can show it.
            missing_bks.append(table_name)
            continue

        bk = _detect_business_key(cols)
        if bk is None:
            missing_bks.append(table_name)

        tables.append(
            BronzeTable(
                catalog=catalog,
                schema_name=schema_name,
                name=table_name,
                columns=cols,
                business_key=bk,
            )
        )

    return BronzeSnapshot(
        catalog=catalog,
        schema_name=schema_name,
        captured_at=datetime.now(timezone.utc),
        tables=tuple(tables),
        missing_business_keys=tuple(missing_bks),
    )
