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


class BvSatellite(BaseModel):
    """Derived / business-rule satellite proposal.

    Unlike a raw-vault satellite, the payload columns here are *new*
    expressions (``computed_columns``) the LLM proposes, not source
    columns. The Validator and the YAML Generator will refuse a BvSatellite
    whose computed columns collide with raw-vault payload columns.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, description="dbt model name, e.g. ``bv_sat_terminal_score``.")
    parent_hub: str = Field(min_length=1)
    source_models: tuple[str, ...] = Field(
        min_length=1,
        description="Raw-vault models this BV sat reads from.",
    )
    computed_columns: tuple[str, ...] = Field(
        min_length=1,
        description="Names of derived columns produced by the BV sat.",
    )
    rationale: str = Field(default="", max_length=2000)


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
