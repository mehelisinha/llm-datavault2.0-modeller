"""Input contracts: source-system metadata fed to the modelling agents.

These models are produced by :mod:`dbt_builder.src.ai.discovery` from offline
sources (YAML metadata, dbt manifests, Spark catalog snapshots, sample CSVs)
and consumed by Phase 2 LLM agents that propose Data Vault 2 entities.

Design notes
------------
* All models are immutable (``model_config = ConfigDict(frozen=True)``) so they
  are safe to hash, cache, and pass between threads / processes.
* Field names use snake_case and align with the existing
  ``poc/metadata/iec_cim_metadata.yaml`` vocabulary so Phase 2 output can be
  emitted as the same YAML shape consumed by ``MetadataReader``.
* ``InferredType`` is a closed enum to keep LLM prompts deterministic; raw
  database type strings remain available on :attr:`SourceColumn.raw_dtype`.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InferredType(str, Enum):
    """Coarse-grained semantic type used by the modelling agents.

    Mapped from raw database / pandas dtypes by the column profiler. Kept
    intentionally small: a richer taxonomy would explode the prompt space
    without improving entity-assignment quality at this stage.
    """

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    UUID = "uuid"
    JSON = "json"
    UNKNOWN = "unknown"


class ColumnProfile(BaseModel):
    """Empirical statistics for a single source column.

    Computed offline by :mod:`dbt_builder.src.ai.discovery.column_profiler`.
    All ratios are bounded to ``[0.0, 1.0]`` by the profiler; field validators
    enforce the contract at construction time so LLM-generated profiles cannot
    smuggle out-of-range values into downstream code.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    row_count: int = Field(ge=0, description="Number of rows scanned.")
    null_count: int = Field(ge=0, description="Number of null values.")
    distinct_count: int = Field(
        ge=0,
        description="Number of distinct non-null values observed in the sample.",
    )
    null_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="null_count / row_count (0 when row_count is 0).",
    )
    cardinality_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "distinct_count / non_null_count. 1.0 indicates a candidate key; "
            "values close to 0 indicate categorical / low-cardinality columns."
        ),
    )
    sample_values: tuple[str, ...] = Field(
        default=(),
        description="Up to N distinct sample values (stringified, truncated).",
    )
    is_likely_key: bool = Field(
        default=False,
        description=(
            "True when null_rate is 0 and cardinality_ratio is at or near 1. "
            "A heuristic signal for the modelling agent, not a guarantee."
        ),
    )

    @field_validator("sample_values")
    @classmethod
    def _no_long_samples(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        # Cap individual sample length so a single fat blob cannot bloat prompts.
        max_len = 200
        return tuple(v[:max_len] for v in values)


class SourceColumn(BaseModel):
    """A single column in a source table, with optional profile."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, description="Column name as it appears in the source.")
    raw_dtype: str = Field(
        min_length=1,
        description="Unmodified database / pandas dtype string (e.g. 'varchar(64)').",
    )
    inferred_type: InferredType = Field(
        default=InferredType.UNKNOWN,
        description="Coarse semantic type derived from raw_dtype and samples.",
    )
    nullable: bool = Field(default=True, description="Whether the source schema allows NULL.")
    description: str | None = Field(
        default=None,
        description="Human-authored description from the source catalogue, if any.",
    )
    ordinal_position: int | None = Field(
        default=None,
        ge=0,
        description="Zero-based ordinal in the source table, if known.",
    )
    profile: ColumnProfile | None = Field(
        default=None,
        description="Empirical statistics; None when the column was not profiled.",
    )


class SourceTable(BaseModel):
    """A single source table with its columns and (optional) sample size."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, description="Table name (no catalog/schema prefix).")
    schema_name: str | None = Field(
        default=None,
        description="Schema containing the table (e.g. 'bronze').",
    )
    catalog: str | None = Field(
        default=None,
        description="Catalog containing the schema (e.g. 'edh_unreg_silver_dev_st').",
    )
    description: str | None = Field(
        default=None,
        description="Human-authored description of the table, if any.",
    )
    columns: tuple[SourceColumn, ...] = Field(
        default=(),
        description="Columns in declaration order. Tuple keeps the model frozen.",
    )
    profiled_row_count: int | None = Field(
        default=None,
        ge=0,
        description="Rows used to compute column profiles; None if not profiled.",
    )

    @field_validator("columns")
    @classmethod
    def _unique_column_names(cls, value: tuple[SourceColumn, ...]) -> tuple[SourceColumn, ...]:
        names = [c.name.lower() for c in value]
        if len(names) != len(set(names)):
            duplicates = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"Duplicate column names in table: {duplicates}")
        return value

    @property
    def fully_qualified_name(self) -> str:
        """Return ``catalog.schema.table`` skipping any unset prefix segments."""
        parts = [p for p in (self.catalog, self.schema_name, self.name) if p]
        return ".".join(parts)


class SourceSystem(BaseModel):
    """Metadata about the upstream source system (mirrors poc YAML 'system')."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_id: str = Field(min_length=1)
    system_name: str = Field(min_length=1)
    source_type: str = Field(default="delta", min_length=1)
    catalog: str | None = None
    schema_name: str | None = None
    record_source: str | None = Field(
        default=None,
        description="Value to stamp into the RECORD_SOURCE column downstream.",
    )


class DiscoveryPayload(BaseModel):
    """The complete input passed to a Phase 2 modelling agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    system: SourceSystem
    tables: tuple[SourceTable, ...] = Field(
        default=(),
        description="Tables discovered in the source system.",
    )

    @field_validator("tables")
    @classmethod
    def _unique_table_names(cls, value: tuple[SourceTable, ...]) -> tuple[SourceTable, ...]:
        keys = [t.fully_qualified_name.lower() for t in value]
        if len(keys) != len(set(keys)):
            duplicates = sorted({k for k in keys if keys.count(k) > 1})
            raise ValueError(f"Duplicate fully-qualified table names: {duplicates}")
        return value

    def get_table(self, name: str) -> SourceTable | None:
        """Look up a table by its bare or fully-qualified name (case-insensitive)."""
        target = name.lower()
        for table in self.tables:
            if table.name.lower() == target or table.fully_qualified_name.lower() == target:
                return table
        return None
