"""Heuristic detection of audit / load / CDC sidecar columns.

These columns must never be considered for business-key inference because their
cardinality is incidental (load timestamp) or technical (CDC LSN). The list is
intentionally small and case-insensitive: both exact name matches and prefix
matches are supported.

Callers can:

* Use :func:`is_system_column` for the default heuristic.
* Pass ``is_system: true`` in YAML to force-flag a column the heuristic misses.
* Pass ``is_system: false`` in YAML to opt a column back in.
"""

from __future__ import annotations

# Exact names (lower-cased) that are always system columns.
_EXACT_NAMES: frozenset[str] = frozenset(
    {
        # DWA / Data Vault audit columns
        "record_source",
        "load_date",
        "load_datetime",
        "load_ts",
        "loaded_at",
        "dl_loaded_at",
        "dl_load_date",
        "dl_load_ts",
        "ingestion_timestamp",
        "ingest_ts",
        "etl_load_ts",
        "_loaded_at",
        # Common audit columns from upstream systems
        "created_at",
        "updated_at",
        "modified_at",
        "deleted_at",
        "sys_created_on",
        "sys_updated_on",
        "sys_mod_count",
    }
)

# Prefixes (lower-cased) — covers CDC sidecar columns and similar conventions.
_PREFIXES: tuple[str, ...] = (
    "__$",  # SQL Server CDC sidecars: __$start_lsn, __$end_lsn, __$seqval, ...
    "_dl_",  # internal DWA load helpers
    "dl__",
)


def is_system_column(name: str) -> bool:
    """Return True when ``name`` matches any known system-column convention."""
    if not name:
        return False
    lowered = name.strip().lower()
    if lowered in _EXACT_NAMES:
        return True
    return any(lowered.startswith(p) for p in _PREFIXES)
