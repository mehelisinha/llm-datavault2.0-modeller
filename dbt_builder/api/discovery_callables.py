"""Resolve catalog callables for snapshot / pipeline runs by ``discovery_mode``.

The discovery listing endpoints and the pipeline orchestrator must use the
same data source. When ``discovery_mode='databricks'`` the UI lists live
Unity Catalog objects, so pipeline runs must call UC REST too — not the stub
YAML adapter (which only knows about ``poc/metadata/*`` fixtures).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from dbt_builder.api import databricks_uc
from dbt_builder.api.settings import ApiSettings
from dbt_builder.api.stub_catalog import make_stub_callables_for_catalog

if TYPE_CHECKING:
    pass

# Callable shapes expected by catalog_inspector / bronze_reader.
ListEntities = Callable[[str, str], list[tuple[str, str]]]
DescribeVault = Callable[[str, str, str], list[tuple[str, str, bool, str | None]]]
ListTables = Callable[[str, str], list[str]]
DescribeBronze = Callable[[str, str, str], list[tuple[str, str, bool, str | None, bool]]]

SnapshotCallables = tuple[ListEntities, DescribeVault, ListTables, DescribeBronze]


def tables_to_include_patterns(
    tables: tuple[str, ...],
    include_patterns: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Convert an explicit table allowlist to full-match regex patterns.

    When ``tables`` is non-empty it takes precedence over ``include_patterns``.
    Table names are escaped so special characters cannot corrupt the pattern.
    """
    if tables:
        return tuple(re.escape(t) for t in tables)
    return include_patterns


def resolve_snapshot_callables(
    settings: ApiSettings,
    *,
    catalog: str,
    bronze_schema: str,
    vault_schema: str | None = None,
) -> SnapshotCallables:
    """Return the four callables for the configured ``discovery_mode``.

    Parameters
    ----------
    catalog, bronze_schema
        Target Unity Catalog location for bronze reads.
    vault_schema
        Vault schema name when inspecting existing DV objects. Passed through
        to the databricks adapter only; stub mode always returns an empty vault.
    """
    mode = settings.discovery_mode
    if mode == "stub":
        return make_stub_callables_for_catalog(catalog, settings.metadata_dir)

    if mode == "databricks":
        client = databricks_uc.get_workspace_client(settings)
        return databricks_uc.make_snapshot_callables(
            client,
            catalog=catalog,
            vault_schema=vault_schema or bronze_schema,
            bronze_schema=bronze_schema,
        )

    # spark mode (default fallback)
    return _make_spark_snapshot_callables()


def _make_spark_snapshot_callables() -> SnapshotCallables:
    """Build Spark SQL callables (Databricks Connect / cluster session)."""
    from shared.utils.spark import get_spark

    spark = get_spark()

    def list_entities(catalog: str, schema_name: str) -> list[tuple[str, str]]:
        rows = spark.sql(f"SHOW TABLES IN `{catalog}`.`{schema_name}`").collect()
        return [(str(row.tableName), str(row.tableType or "TABLE")) for row in rows]

    def describe_vault(
        catalog: str, schema_name: str, table: str
    ) -> list[tuple[str, str, bool, str | None]]:
        rows = spark.sql(f"DESCRIBE TABLE `{catalog}`.`{schema_name}`.`{table}`").collect()
        return [
            (
                str(row.col_name),
                str(row.data_type),
                bool(row.nullable),
                getattr(row, "comment", None),
            )
            for row in rows
            if row.col_name and not str(row.col_name).startswith("#")
        ]

    def list_tables(catalog: str, schema_name: str) -> list[str]:
        rows = spark.sql(f"SHOW TABLES IN `{catalog}`.`{schema_name}`").collect()
        return [str(row.tableName) for row in rows]

    def describe_bronze(
        catalog: str, schema_name: str, table: str
    ) -> list[tuple[str, str, bool, str | None, bool]]:
        rows = spark.sql(f"DESCRIBE TABLE `{catalog}`.`{schema_name}`.`{table}`").collect()
        return [
            (
                str(row.col_name),
                str(row.data_type),
                bool(row.nullable),
                getattr(row, "comment", None),
                bool(getattr(row, "is_partition", False)),
            )
            for row in rows
            if row.col_name and not str(row.col_name).startswith("#")
        ]

    return list_entities, describe_vault, list_tables, describe_bronze
