"""Business-vault contracts produced by the BV Architect agent.

The raw-vault layer (Hubs, Links, Satellites) is captured by
:class:`~dbt_builder.src.ai.contracts.decisions.ModelingPlan`. The business
vault sits on top and provides query-friendly aggregations:

* **PIT (point-in-time)**: one row per hub key per snapshot timestamp,
  joining the latest valid satellite versions. One PIT per hub-with-≥2
  satellites is the deterministic baseline.
* **Bridge**: pre-computed many-to-many resolutions across links. One
  bridge per link with ≥2 hub references.
* **Business-vault Satellite**: derived / computed payloads (rules,
  enrichments, metrics). These need domain reasoning — a typed proposal
  schema is provided so an LLM can fill them in safely.

All models are frozen so they can be hashed, cached, and diffed for the
byte-equality snapshot tests the YAML Generator relies on.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BvKind(str, Enum):
    PIT = "pit"
    BRIDGE = "bridge"
    BV_SAT = "bv_sat"


class PitTable(BaseModel):
    """Point-in-time table proposal — one per hub with multiple satellites."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, description="dbt model name, e.g. ``pit_terminal``.")
    parent_hub: str = Field(min_length=1)
    satellites: tuple[str, ...] = Field(
        min_length=1,
        description="Names of satellite models the PIT joins.",
    )
    granularity: str = Field(
        default="day",
        description="Snapshot grain; commonly 'day' or 'hour'. Free-form for now.",
    )
    rationale: str = Field(default="", max_length=2000)

    @field_validator("satellites")
    @classmethod
    def _unique_satellites(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError(f"Duplicate satellite names in PIT: {value}")
        return value


class BridgeTable(BaseModel):
    """Bridge table proposal — one per link with ≥2 hub references."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, description="dbt model name, e.g. ``br_terminal_node``.")
    parent_link: str = Field(min_length=1)
    hub_keys: tuple[str, ...] = Field(
        min_length=2,
        description="Ordered hub names the bridge resolves between.",
    )
    rationale: str = Field(default="", max_length=2000)


class BvSatPayloadItem(BaseModel):
    """One derived column on a BV satellite, with optional inline SQL.

    The ``derivation_sql`` string, when present, is emitted alongside the
    column in the generated YAML so downstream consumers (and humans
    reviewing the YAML) can see the rule that produces the value. It is
    a structural hint — the actual SQL is realised by the dbt model the
    YAML drives; this field is documentation embedded in metadata.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, description="Derived column name.")
    derivation_sql: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Optional inline SQL expression that produces the column. "
            "Free-form; not parsed at contract time. The BV-sat validator "
            "checks any column names referenced here exist on the source "
            "raw-vault models."
        ),
    )


class BvSatClassification(str, Enum):
    """Coarse category of derivation a BV satellite performs.

    Used by the pattern-gated proposer to keep BV-sat suggestions
    auditable: every proposal carries the rule family it belongs to so
    reviewers can spot mismatches between the rule and the columns.
    """

    NORMALISATION = "normalisation"
    CLASSIFICATION = "classification"
    ENRICHMENT = "enrichment"


class BvSatellite(BaseModel):
    """Derived / business-rule satellite proposal.

    Unlike a raw-vault satellite, the payload columns here are *new*
    expressions the LLM (or a deterministic pattern detector) proposes,
    not source columns. The Validator and the YAML Generator will refuse
    a BvSatellite whose derived columns collide with raw-vault payload
    columns.

    Two payload shapes are supported for back-compat:

    * ``payload`` — preferred. A tuple of :class:`BvSatPayloadItem` with
      optional ``derivation_sql`` per column. Renderers that understand
      this field can emit the SQL hint alongside the column.
    * ``computed_columns`` — legacy. A tuple of bare column names. Kept
      so existing tests and external callers do not break.

    At least one of the two MUST be non-empty. When both are populated,
    ``payload`` takes precedence and ``computed_columns`` is treated as
    a deprecated mirror.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, description="dbt model name, e.g. ``bv_sat_terminal_score``.")
    parent_hub: str = Field(min_length=1)
    source_models: tuple[str, ...] = Field(
        min_length=1,
        description="Raw-vault models this BV sat reads from.",
    )
    payload: tuple[BvSatPayloadItem, ...] = Field(
        default=(),
        description=(
            "Derived columns with optional inline derivation SQL. Preferred "
            "over ``computed_columns`` for new code."
        ),
    )
    computed_columns: tuple[str, ...] = Field(
        default=(),
        description=(
            "Legacy: bare names of derived columns. Kept for back-compat "
            "with callers that pre-date :class:`BvSatPayloadItem`. New "
            "code should populate ``payload`` instead."
        ),
    )
    classification: BvSatClassification | None = Field(
        default=None,
        description=(
            "Rule family this BV sat applies. Set by the pattern-gated "
            "proposer; ``None`` when the satellite was hand-crafted or "
            "produced by a generator that does not classify."
        ),
    )
    rationale: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _require_at_least_one_payload(self) -> BvSatellite:
        if not self.payload and not self.computed_columns:
            raise ValueError(
                f"BvSatellite '{self.name}' must declare either 'payload' "
                "or 'computed_columns' (at least one column)."
            )
        return self

    @property
    def effective_payload(self) -> tuple[BvSatPayloadItem, ...]:
        """Return ``payload`` when present, else lift ``computed_columns``.

        Use this in renderers and validators that need a uniform view of
        the column set regardless of which field the caller populated.
        """
        if self.payload:
            return self.payload
        return tuple(BvSatPayloadItem(name=c) for c in self.computed_columns)

    @property
    def column_names(self) -> tuple[str, ...]:
        """Names of all derived columns regardless of payload shape."""
        return tuple(item.name for item in self.effective_payload)


class BvProposal(BaseModel):
    """Aggregate output of the BV Architect."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_id: str = Field(min_length=1)
    pit_tables: tuple[PitTable, ...] = ()
    bridge_tables: tuple[BridgeTable, ...] = ()
    bv_satellites: tuple[BvSatellite, ...] = ()

    @model_validator(mode="after")
    def _check_unique_names(self) -> BvProposal:
        names: list[str] = []
        names.extend(p.name for p in self.pit_tables)
        names.extend(b.name for b in self.bridge_tables)
        names.extend(s.name for s in self.bv_satellites)
        if len(set(names)) != len(names):
            duplicates = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"Duplicate BV object names: {duplicates}")
        return self

    @property
    def is_empty(self) -> bool:
        return not (self.pit_tables or self.bridge_tables or self.bv_satellites)

    @property
    def object_count(self) -> int:
        return len(self.pit_tables) + len(self.bridge_tables) + len(self.bv_satellites)
