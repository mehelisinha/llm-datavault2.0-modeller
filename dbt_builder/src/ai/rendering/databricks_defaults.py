"""Databricks / Delta Lake per-entity-type configuration templates.

Every ``databricks_config`` block in the v3 metadata YAML follows the same
pattern for a given entity kind (hub, satellite, link, …). Rather than
repeating the same property set in each emitter function, this module
owns all defaults in one place.

Callers receive a fully-formed ``dict`` they can embed directly in a YAML
document — no string literals need to exist anywhere else.

All numeric and string constants are defined as module-level names so tests
can assert exact values and future changes are made in exactly one place.
"""

from __future__ import annotations

from typing import Any

# ── Shared Delta property constants ───────────────────────────────────────────

TARGET_FILE_SIZE: int = 134_217_728  # 128 MB
LOG_RETENTION: str = "interval 30 days"
FILE_RETENTION: str = "interval 7 days"
SKIPPING_INDEXED_COLS: int = 8
# Hubs index fewer columns than other entities (only HK + LOAD_DATE matter for
# pruning). Per the DV2 Raw Vault skill: Hub = 4, Satellite/Link/Eff_sat = 8.
HUB_SKIPPING_INDEXED_COLS: int = 4
LOAD_DATE_COL: str = "LOAD_DATE"
# The DV2 Business Vault skill mandates AS_OF_DATE (NEVER SNAPSHOT_DATE) as the
# PIT snapshot-date column name, used identically in as_of_dates, every PIT's
# as_of_dates_table.date_column, PIT cluster_by, and PIT dataSkippingStatsColumns.
AS_OF_DATE_COL: str = "AS_OF_DATE"
END_DATE_COL: str = "END_DATE"

# Properties shared by every incremental append-only entity.
_DELTA_BASE: dict[str, Any] = {
    "delta.autoOptimize.optimizeWrite": True,
    "delta.autoOptimize.autoCompact": True,
    "delta.targetFileSize": TARGET_FILE_SIZE,
    "delta.tuneFileSizesForRewrites": True,
    "delta.logRetentionDuration": LOG_RETENTION,
    "delta.deletedFileRetentionDuration": FILE_RETENTION,
    "delta.dataSkippingNumIndexedCols": SKIPPING_INDEXED_COLS,
}

# Extra properties for entities that are strictly insert-only.
_APPEND_ONLY: dict[str, Any] = {
    "delta.enableDeletionVectors": False,
    "delta.appendOnly": True,
}


# ── Private builder ───────────────────────────────────────────────────────────


def _incremental_append(
    cluster_by: list[str],
    skipping_stats_cols: str,
    on_schema_change: str = "append_new_columns",
    indexed_cols: int = SKIPPING_INDEXED_COLS,
) -> dict[str, Any]:
    """Return an incremental/append databricks_config block.

    ``indexed_cols`` overrides ``delta.dataSkippingNumIndexedCols`` for entity
    kinds that index fewer columns (hubs use 4, everything else 8).
    """
    return {
        "materialized": "incremental",
        "incremental_strategy": "append",
        "on_schema_change": on_schema_change,
        "cluster_by": cluster_by,
        "table_properties": {
            **_DELTA_BASE,
            **_APPEND_ONLY,
            "delta.dataSkippingNumIndexedCols": indexed_cols,
            "delta.dataSkippingStatsColumns": skipping_stats_cols,
        },
    }


# ── Public per-kind builders ──────────────────────────────────────────────────


def hub_config(hash_key: str) -> dict[str, Any]:
    """Delta config for a raw-vault hub (incremental / append-only)."""
    return _incremental_append(
        cluster_by=[hash_key],
        skipping_stats_cols=f"{hash_key},{LOAD_DATE_COL}",
        indexed_cols=HUB_SKIPPING_INDEXED_COLS,
    )


def satellite_config(hash_key: str, hashdiff: str) -> dict[str, Any]:
    """Delta config for a raw-vault satellite (incremental / append-only)."""
    return _incremental_append(
        cluster_by=[hash_key, LOAD_DATE_COL],
        skipping_stats_cols=f"{hash_key},{LOAD_DATE_COL},{hashdiff}",
    )


def link_config(hash_key: str, driving_fk: str) -> dict[str, Any]:
    """Delta config for a raw-vault link (incremental / append-only)."""
    return _incremental_append(
        cluster_by=[hash_key, driving_fk],
        skipping_stats_cols=f"{hash_key},{driving_fk},{LOAD_DATE_COL}",
    )


def eff_sat_config(hash_key: str) -> dict[str, Any]:
    """Delta config for an effectivity satellite (incremental / merge).

    Merge strategy is required because END_DATE updates need true MERGE
    semantics — appendOnly must NOT be set.
    """
    return {
        "materialized": "incremental",
        "incremental_strategy": "merge",
        "unique_key": hash_key,
        "on_schema_change": "append_new_columns",
        "cluster_by": [hash_key, END_DATE_COL],
        "table_properties": {
            **_DELTA_BASE,
            # No appendOnly — merge rewrites need update capability.
            "delta.enableDeletionVectors": False,
            "delta.dataSkippingStatsColumns": (
                f"{hash_key},{END_DATE_COL},{LOAD_DATE_COL}"
            ),
        },
    }


def staging_config() -> dict[str, Any]:
    """Delta config for a staging model (view — transient, no persistence)."""
    return {"materialized": "view"}


def pit_config(hub_hk: str) -> dict[str, Any]:
    """Delta config for a point-in-time table (incremental / insert_overwrite)."""
    return {
        "materialized": "incremental",
        "incremental_strategy": "insert_overwrite",
        "on_schema_change": "append_new_columns",
        "cluster_by": [hub_hk, AS_OF_DATE_COL],
        "table_properties": {
            **_DELTA_BASE,
            "delta.dataSkippingStatsColumns": f"{hub_hk},{AS_OF_DATE_COL}",
        },
    }


def bridge_config(hub_hk: str, link_hk: str) -> dict[str, Any]:
    """Delta config for a bridge table (full-refresh table)."""
    return {
        "materialized": "table",
        "table_properties": {
            **_DELTA_BASE,
            "delta.dataSkippingStatsColumns": f"{link_hk},{hub_hk},{LOAD_DATE_COL}",
        },
    }


def dim_config() -> dict[str, Any]:
    """Delta config for a dimension view (computed on read)."""
    return {"materialized": "view"}


def fact_config() -> dict[str, Any]:
    """Delta config for a fact view (computed on read)."""
    return {"materialized": "view"}


def bv_sat_config(hash_key: str, hashdiff: str) -> dict[str, Any]:
    """Delta config for a business-vault satellite (same pattern as raw satellite)."""
    return _incremental_append(
        cluster_by=[hash_key, LOAD_DATE_COL],
        skipping_stats_cols=f"{hash_key},{LOAD_DATE_COL},{hashdiff}",
    )


def global_optimization() -> dict[str, Any]:
    """Top-level ``databricks_optimization`` block: global Delta defaults."""
    return {
        "default_file_size": TARGET_FILE_SIZE,
        "log_retention": LOG_RETENTION,
        "deleted_file_retention": FILE_RETENTION,
        "auto_optimize": {
            "optimize_write": True,
            "auto_compact": True,
        },
        "liquid_clustering": {
            "enabled": True,
            "preferred_over_zorder": True,
        },
        "skipping_indexed_cols": SKIPPING_INDEXED_COLS,
        # Default incremental strategy per entity kind (can be overridden per entity).
        "incremental_strategy_defaults": {
            "hub": "append",
            "satellite_raw": "append",
            "satellite_bv": "append",
            "link": "append",
            "eff_sat": "merge",
            "pit": "insert_overwrite",
            "bridge": "table",
            "staging": "view",
            "dim": "view",
            "fact": "view",
        },
    }
