"""Read source-system schemas from offline metadata files.

This module provides two entry points:

* :func:`discover_from_yaml` — read a YAML file in the schema described below
  and return a :class:`DiscoveryPayload`.
* :func:`discover_from_dict` — same, starting from an already-loaded mapping.
  Useful for unit tests and for callers that have constructed the metadata
  programmatically.

Expected YAML shape
-------------------
.. code-block:: yaml

    system:
      system_id: IEC_CIM_001
      system_name: IEC61968_CIM
      catalog: edh_unreg_silver_dev_st
      schema: bronze
      record_source: IEC61968_CIM_v2.0

    tables:
      - name: conducting_equipment
        description: Physical grid assets that conduct electricity.
        columns:
          - {name: mrid,           raw_dtype: varchar(64), nullable: false,
             description: Master resource identifier.}
          - {name: name,           raw_dtype: varchar(255)}
          - {name: equipment_type, raw_dtype: varchar(64)}

The shape is intentionally a strict subset of what a future Spark / dbt
manifest reader can emit, so the rest of the AI pipeline does not care where
the discovery payload came from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from dbt_builder.src.ai.contracts.payloads import (
    DiscoveryPayload,
    InferredType,
    SourceColumn,
    SourceSystem,
    SourceTable,
)
from dbt_builder.src.ai.discovery.system_columns import is_system_column

# Default source_type stamped on a SourceSystem when YAML / caller omits it.
# Lives here (rather than in spark_discovery) so both adapters share it.
DEFAULT_SOURCE_TYPE = "delta"

# Mapping from raw dtype prefixes to coarse semantic types. Order matters: the
# first prefix that matches wins, so put longer / more specific prefixes first.
_DTYPE_PREFIX_MAP: tuple[tuple[str, InferredType], ...] = (
    ("timestamp", InferredType.TIMESTAMP),
    ("datetime", InferredType.TIMESTAMP),
    ("date", InferredType.DATE),
    ("uuid", InferredType.UUID),
    ("json", InferredType.JSON),
    ("bool", InferredType.BOOLEAN),
    ("varchar", InferredType.STRING),
    ("char", InferredType.STRING),
    ("string", InferredType.STRING),
    ("text", InferredType.STRING),
    ("bigint", InferredType.INTEGER),
    ("int", InferredType.INTEGER),
    ("smallint", InferredType.INTEGER),
    ("tinyint", InferredType.INTEGER),
    ("long", InferredType.INTEGER),
    ("decimal", InferredType.FLOAT),
    ("numeric", InferredType.FLOAT),
    ("double", InferredType.FLOAT),
    ("float", InferredType.FLOAT),
)


def infer_type(raw_dtype: str) -> InferredType:
    """Map a raw dtype string (case-insensitive) to a coarse semantic type.

    Public so other discovery adapters (e.g. Spark) can share the mapping
    without reaching into a private symbol.
    """
    lowered = raw_dtype.strip().lower()
    for prefix, inferred in _DTYPE_PREFIX_MAP:
        if lowered.startswith(prefix):
            return inferred
    return InferredType.UNKNOWN


# Backwards-compatible private alias (kept so existing call sites keep working
# until any future refactor; new code should call ``infer_type``).
_infer_type = infer_type


def build_source_column(
    name: str,
    raw_dtype: str,
    *,
    nullable: bool = True,
    description: str | None = None,
    ordinal: int | None = None,
    is_system: bool | None = None,
) -> SourceColumn:
    """Construct a :class:`SourceColumn` with consistent type / system inference.

    Used by every discovery adapter so YAML, Spark, and future sources never
    drift on how columns are normalised.

    Parameters
    ----------
    name, raw_dtype
        Column identity. Both required.
    nullable, description, ordinal
        Optional column attributes carried through to the contract.
    is_system
        Explicit override for the ``is_system`` flag. ``None`` means "apply the
        :func:`is_system_column` heuristic".
    """
    resolved_is_system = is_system_column(name) if is_system is None else bool(is_system)
    return SourceColumn(
        name=name,
        raw_dtype=raw_dtype,
        inferred_type=infer_type(raw_dtype),
        nullable=nullable,
        description=description,
        ordinal_position=ordinal,
        is_system=resolved_is_system,
    )


def _build_column(raw: dict[str, Any], ordinal: int) -> SourceColumn:
    if "name" not in raw or "raw_dtype" not in raw:
        raise ValueError(
            f"Column at ordinal {ordinal} is missing required keys 'name' / 'raw_dtype'"
        )
    return build_source_column(
        name=str(raw["name"]),
        raw_dtype=str(raw["raw_dtype"]),
        nullable=bool(raw.get("nullable", True)),
        description=raw.get("description"),
        ordinal=ordinal,
        # YAML override wins over the heuristic in either direction.
        is_system=raw["is_system"] if "is_system" in raw else None,
    )


def _build_table(raw: dict[str, Any], system: SourceSystem) -> SourceTable:
    if "name" not in raw or "columns" not in raw:
        raise ValueError(f"Table entry is missing required keys 'name' / 'columns': {raw!r}")
    columns = tuple(_build_column(col, ordinal=i) for i, col in enumerate(raw["columns"]))
    return SourceTable(
        name=str(raw["name"]),
        schema_name=raw.get("schema_name") or system.schema_name,
        catalog=raw.get("catalog") or system.catalog,
        description=raw.get("description"),
        columns=columns,
    )


def _build_system(raw: dict[str, Any]) -> SourceSystem:
    if "system_id" not in raw or "system_name" not in raw:
        raise ValueError("system block is missing required keys 'system_id' / 'system_name'")
    return SourceSystem(
        system_id=str(raw["system_id"]),
        system_name=str(raw["system_name"]),
        source_type=str(raw.get("source_type", DEFAULT_SOURCE_TYPE)),
        catalog=raw.get("catalog"),
        # Accept both 'schema' (legacy YAML) and 'schema_name' (Pydantic field).
        schema_name=raw.get("schema_name") or raw.get("schema"),
        record_source=raw.get("record_source"),
    )


def discover_from_dict(data: dict[str, Any]) -> DiscoveryPayload:
    """Build a :class:`DiscoveryPayload` from an already-loaded mapping.

    Raises
    ------
    ValueError
        When required keys are missing or the data shape is invalid. The
        underlying :class:`pydantic.ValidationError` may also propagate when
        Pydantic's own field-level validation fails (e.g. duplicate columns).
    """
    if "system" not in data:
        raise ValueError("metadata is missing required top-level key 'system'")
    system = _build_system(data["system"])
    tables_raw = data.get("tables") or ()
    if not isinstance(tables_raw, list):
        raise ValueError("'tables' must be a list when present")
    tables = tuple(_build_table(t, system) for t in tables_raw)
    return DiscoveryPayload(system=system, tables=tables)


def discover_from_yaml(path: str | Path) -> DiscoveryPayload:
    """Load a YAML metadata file from ``path`` and return a discovery payload.

    The file must contain a top-level ``system`` mapping and an optional
    ``tables`` list. See the module docstring for the exact shape.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"metadata file not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"metadata YAML must be a mapping at the top level: {file_path}")
    return discover_from_dict(data)
