"""Output contracts: Data Vault 2 entity decisions emitted by the LLM agents.

A Phase 2 modelling agent consumes a :class:`DiscoveryPayload` and returns a
:class:`ModelingPlan` containing zero or more hub / link / satellite decisions.
The plan is then validated, optionally reviewed by a human, and finally rendered
into dbt YAML / SQL by the existing ``MetadataReader`` + ``DVGenerator`` pipeline.

The shapes here are deliberately close to the YAML keys consumed by
``poc/metadata/iec_cim_metadata.yaml`` so the rendering step is a thin mapping
rather than a translation.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EntityKind(str, Enum):
    """Closed taxonomy of Data Vault 2 raw-vault entity kinds."""

    HUB = "hub"
    LINK = "link"
    SATELLITE = "satellite"


class DecisionConfidence(str, Enum):
    """Coarse self-reported confidence from the modelling agent.

    Kept ordinal (LOW / MEDIUM / HIGH) rather than numeric to discourage
    over-precision in LLM output and to make human review thresholds simple.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class _BaseDecision(BaseModel):
    """Common fields shared by every entity decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        min_length=1,
        description="Target dbt model name, e.g. 'hub_conducting_equipment'.",
    )
    source_table: str = Field(
        min_length=1,
        description="Bare source table name (catalog/schema qualifiers stripped).",
    )
    confidence: DecisionConfidence = DecisionConfidence.MEDIUM
    rationale: str = Field(
        default="",
        max_length=2000,
        description="Free-text justification produced by the agent (kept short).",
    )

    @field_validator("source_table", mode="before")
    @classmethod
    def _strip_qualifier(cls, value: object) -> object:
        # LLMs occasionally echo back the fully-qualified name they saw in
        # the discovery payload (e.g. "catalog.schema.table") even when the
        # prompt asks for the bare name. Downstream renderers compose
        # staging-model names as `stg_{source_table}`, which produces
        # invalid identifiers when qualifiers leak through. Strip here at
        # the contract boundary so every consumer sees the bare name.
        if isinstance(value, str) and "." in value:
            return value.rsplit(".", 1)[-1]
        return value


class HubDecision(_BaseDecision):
    """A proposed raw-vault Hub.

    A hub captures the **business-key identity** of a core entity. The
    ``business_keys`` list normally has length 1; composite keys are allowed
    when the source genuinely has no surrogate.
    """

    kind: EntityKind = Field(default=EntityKind.HUB, frozen=True)
    business_keys: tuple[str, ...] = Field(
        min_length=1,
        description="Source column(s) forming the business key.",
    )
    hash_key: str = Field(
        min_length=1,
        description="Deterministic hash key column name, e.g. 'HK_CONDUCTING_EQUIPMENT'.",
    )

    @field_validator("kind")
    @classmethod
    def _kind_is_hub(cls, value: EntityKind) -> EntityKind:
        if value is not EntityKind.HUB:
            raise ValueError("HubDecision.kind must be EntityKind.HUB")
        return value


class SatelliteDecision(_BaseDecision):
    """A proposed raw-vault Satellite hanging off exactly one parent hub.

    Rate-of-change splitting
    ------------------------
    A hub MAY have more than one satellite when its descriptive columns
    fall into clearly different change velocities (e.g. quasi-static
    registration data vs frequently changing operational flags). When the
    modeller chooses to split, it names the resulting satellites with a
    ``subgroup`` suffix (``_details`` / ``_operational`` / ``_measurements``)
    and records ``change_velocity`` so reviewers can audit the decision.
    The :class:`ModelingPlan` validator caps the split at 3 satellites
    per hub to prevent over-fragmentation.
    """

    kind: EntityKind = Field(default=EntityKind.SATELLITE, frozen=True)
    parent_hub: str = Field(
        min_length=1,
        description="Name of the parent HubDecision this satellite describes.",
    )
    hash_key: str = Field(
        min_length=1,
        description="Hash-key column inherited from the parent hub.",
    )
    hashdiff: str = Field(
        min_length=1,
        description="Hashdiff column protecting the descriptive payload.",
    )
    payload: tuple[str, ...] = Field(
        min_length=1,
        description="Descriptive (non-key) source columns tracked by this satellite.",
    )
    effective_from: str | None = Field(
        default=None,
        description="Optional effective-from column for SCD2 semantics.",
    )
    subgroup: Literal["details", "operational", "measurements"] | None = Field(
        default=None,
        description=(
            "Rate-of-change subgroup label. ``details`` covers quasi-static "
            "attributes, ``operational`` covers frequently changing status "
            "/ flag columns, ``measurements`` covers continuous numeric "
            "readings. ``None`` (the default) means the modeller did not "
            "split this hub — a single satellite carries all payload."
        ),
    )
    change_velocity: Literal["static", "dynamic", "mixed"] = Field(
        default="mixed",
        description=(
            "Coarse rate-of-change classification for the payload as a "
            "whole. Modeller heuristic + LLM-confirmed. Used by reviewers "
            "to spot mismatches between the chosen split and the actual "
            "column volatility."
        ),
    )

    @field_validator("kind")
    @classmethod
    def _kind_is_satellite(cls, value: EntityKind) -> EntityKind:
        if value is not EntityKind.SATELLITE:
            raise ValueError("SatelliteDecision.kind must be EntityKind.SATELLITE")
        return value


class LinkDecision(_BaseDecision):
    """A proposed raw-vault Link relating two or more hubs."""

    kind: EntityKind = Field(default=EntityKind.LINK, frozen=True)
    hash_key: str = Field(
        min_length=1,
        description="Composite hash-key column for the link, e.g. 'HK_TERMINAL_EQUIPMENT_NODE'.",
    )
    fk_columns: tuple[str, ...] = Field(
        min_length=2,
        description="Ordered hub hash-key columns participating in the link.",
    )

    @field_validator("kind")
    @classmethod
    def _kind_is_link(cls, value: EntityKind) -> EntityKind:
        if value is not EntityKind.LINK:
            raise ValueError("LinkDecision.kind must be EntityKind.LINK")
        return value


class ModelingPlan(BaseModel):
    """The full set of entity decisions produced for one source system.

    Cross-entity invariants are enforced by ``model_validator``:

    * hub names are unique;
    * every satellite's ``parent_hub`` references a known hub in the same plan;
    * link / satellite names do not collide with hub names.

    These checks let the rendering layer assume a well-formed plan and avoid
    re-validating in multiple downstream steps.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_id: str = Field(min_length=1)
    hubs: tuple[HubDecision, ...] = ()
    links: tuple[LinkDecision, ...] = ()
    satellites: tuple[SatelliteDecision, ...] = ()

    @model_validator(mode="after")
    def _check_cross_entity_invariants(self) -> ModelingPlan:
        hub_names = {h.name for h in self.hubs}
        if len(hub_names) != len(self.hubs):
            raise ValueError("Duplicate hub names in plan")

        link_names = {ln.name for ln in self.links}
        sat_names = {s.name for s in self.satellites}
        all_names = hub_names | link_names | sat_names
        expected = len(self.hubs) + len(self.links) + len(self.satellites)
        if len(all_names) != expected:
            raise ValueError("Entity names collide across hubs / links / satellites")

        # Per-hub satellite cap. Rate-of-change splitting is allowed up to 3
        # satellites per hub (details / operational / measurements). More than
        # that is almost always an over-fragmentation regression where the LLM
        # split on noise. Caught here at the contract boundary so no downstream
        # consumer has to defend against it.
        _SAT_CAP_PER_HUB = 3
        sat_count_per_hub: dict[str, int] = {}
        for sat in self.satellites:
            if sat.parent_hub not in hub_names:
                raise ValueError(
                    f"Satellite '{sat.name}' references unknown parent hub '{sat.parent_hub}'"
                )
            sat_count_per_hub[sat.parent_hub] = sat_count_per_hub.get(sat.parent_hub, 0) + 1
        for hub_name, count in sat_count_per_hub.items():
            if count > _SAT_CAP_PER_HUB:
                raise ValueError(
                    f"Hub '{hub_name}' has {count} satellites; cap is "
                    f"{_SAT_CAP_PER_HUB} (details / operational / measurements)"
                )
        return self

    @property
    def entity_count(self) -> int:
        return len(self.hubs) + len(self.links) + len(self.satellites)
