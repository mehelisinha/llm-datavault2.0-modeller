"""Catalog / bronze / diff contracts produced by the deterministic Steps 1-3.

These models replace the implicit dicts that earlier prototypes shuffled
between catalog inspection, bronze schema reading and diff analysis. They
are the typed surface that the React UI, the FastAPI service facade and the
LLM agents (Schema Analyzer, BV Architect, YAML Generator) all consume.

All models are frozen so they can be hashed for idempotency snapshots and
safely shared across the pipeline boundary without defensive copying.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ─── Catalog (Step 1) ────────────────────────────────────────────────────────


class VaultColumn(BaseModel):
    """A single column in an existing vault Delta table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    raw_dtype: str = Field(min_length=1)
    nullable: bool = True
    comment: str | None = None


class VaultEntity(BaseModel):
    """An existing vault entity (hub / link / satellite / pit / bridge)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    kind: str = Field(min_length=1, description="hub | link | sat | eff_sat | pit | bridge")
    columns: tuple[VaultColumn, ...] = ()

    @field_validator("columns")
    @classmethod
    def _unique_column_names(cls, value: tuple[VaultColumn, ...]) -> tuple[VaultColumn, ...]:
        seen = {c.name.lower() for c in value}
        if len(seen) != len(value):
            raise ValueError(f"Duplicate column names in vault entity: {value}")
        return value


class CatalogSnapshot(BaseModel):
    """Output of Step 1 — Catalog Inspector.

    Captures the *current state* of the target vault schema: every entity
    that already exists in Delta plus the entries already present in the
    repository's ``system_metadata.yml``. The diff analyzer joins this with
    the bronze snapshot to decide what to skip, regenerate or flag.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    captured_at: datetime
    entities: tuple[VaultEntity, ...] = ()
    metadata_yaml_path: str | None = Field(
        default=None,
        description="Path to the existing system_metadata.yml that was parsed, if any.",
    )

    @property
    def entity_names(self) -> frozenset[str]:
        return frozenset(e.name.lower() for e in self.entities)


# ─── Bronze (Step 2) ─────────────────────────────────────────────────────────


class BronzeColumn(BaseModel):
    """A single column described by ``DESCRIBE TABLE`` on the bronze layer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    raw_dtype: str = Field(min_length=1)
    nullable: bool = True
    comment: str | None = None
    is_partition: bool = False


class BronzeTable(BaseModel):
    """A single bronze table snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    name: str = Field(min_length=1)
    columns: tuple[BronzeColumn, ...] = Field(min_length=1)
    business_key: str | None = Field(
        default=None,
        description="Detected business-key column (mrid / *_id / *_key); None if absent.",
    )

    @field_validator("columns")
    @classmethod
    def _unique_column_names(cls, value: tuple[BronzeColumn, ...]) -> tuple[BronzeColumn, ...]:
        names = [c.name.lower() for c in value]
        if len(names) != len(set(names)):
            duplicates = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"Duplicate column names in bronze table: {duplicates}")
        return value

    @property
    def fully_qualified_name(self) -> str:
        return f"{self.catalog}.{self.schema_name}.{self.name}"


class BronzeSnapshot(BaseModel):
    """Output of Step 2 — Bronze Schema Reader."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    captured_at: datetime
    tables: tuple[BronzeTable, ...] = ()
    missing_business_keys: tuple[str, ...] = Field(
        default=(),
        description="Bronze table names that lack a recognisable business-key column.",
    )

    @property
    def table_names(self) -> frozenset[str]:
        return frozenset(t.name.lower() for t in self.tables)


# ─── Diff (Step 3) ───────────────────────────────────────────────────────────


class ChangeCategory(str, Enum):
    """How a single bronze table relates to the existing vault."""

    NEW = "new"  # bronze table has no corresponding vault entity yet
    DRIFT = "drift"  # vault entity exists but column set has changed
    UNCHANGED = "unchanged"  # vault entity exists, columns match — skip
    ORPHANED = "orphaned"  # vault entity exists, no bronze source — flag


class ChangeRisk(str, Enum):
    """Coarse risk level for a single change. Drives pipeline halt vs warn."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ColumnDiff(BaseModel):
    """Per-column diff between bronze and the matching vault entity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    change: str = Field(min_length=1, description="added | removed | type_changed")
    old_dtype: str | None = None
    new_dtype: str | None = None


class TableChange(BaseModel):
    """One row in the diff change-set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    table_name: str = Field(min_length=1)
    category: ChangeCategory
    risk: ChangeRisk = ChangeRisk.LOW
    column_diffs: tuple[ColumnDiff, ...] = ()
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _category_consistency(self) -> TableChange:
        # ORPHANED has no source — column diffs make no sense.
        if self.category is ChangeCategory.ORPHANED and self.column_diffs:
            raise ValueError(
                f"ORPHANED change for '{self.table_name}' must not carry column diffs."
            )
        # UNCHANGED must be a clean no-op.
        if self.category is ChangeCategory.UNCHANGED and self.column_diffs:
            raise ValueError(
                f"UNCHANGED change for '{self.table_name}' must not carry column diffs."
            )
        return self


class ChangeSet(BaseModel):
    """Output of Step 3 — Diff Analyzer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    computed_at: datetime
    changes: tuple[TableChange, ...] = ()

    @property
    def needs_modeling(self) -> tuple[TableChange, ...]:
        """Subset of changes that the Schema Analyzer agent must look at."""
        return tuple(
            c for c in self.changes if c.category in (ChangeCategory.NEW, ChangeCategory.DRIFT)
        )

    @property
    def has_high_risk(self) -> bool:
        return any(c.risk is ChangeRisk.HIGH for c in self.changes)
