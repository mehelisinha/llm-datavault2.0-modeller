"""Offline source-system discovery and profiling.

Two responsibilities:

* :mod:`schema_discovery` reads source-system schema definitions from
  hand-authored YAML metadata files (the format already used in
  ``poc/metadata/iec_cim_metadata.yaml``) and produces a
  :class:`~dbt_builder.src.ai.contracts.payloads.DiscoveryPayload`.
* :mod:`column_profiler` computes empirical
  :class:`~dbt_builder.src.ai.contracts.payloads.ColumnProfile` instances from
  in-memory tabular samples (lists of dicts or pandas DataFrames).

Both are pure / side-effect free at module import time. Spark and Databricks
catalogue support is intentionally *not* part of Phase 1; it can be added in
Phase 2 by implementing additional functions that return the same contract
shapes.
"""

from __future__ import annotations

from dbt_builder.src.ai.discovery.column_profiler import profile_column, profile_table
from dbt_builder.src.ai.discovery.schema_discovery import (
    discover_from_dict,
    discover_from_yaml,
)

__all__ = [
    "discover_from_dict",
    "discover_from_yaml",
    "profile_column",
    "profile_table",
]
