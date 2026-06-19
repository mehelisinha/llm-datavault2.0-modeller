"""Shared, derived entity factories for the AI tests.

Every Data-Vault test needs hubs / links / satellites, and each previously
re-declared its own builders with hand-maintained ``HK_*`` / ``HASHDIFF_*``
literals. That is exactly the kind of duplication that drifts. These factories
*derive* every secondary field from the entity name (the one thing a test
actually cares about), so a test states only what is meaningful to it:

    hash_key  := HK_<name-without-prefix, upper>
    hashdiff  := HASHDIFF_<sat-name, upper>
    fk_columns:= the hub hash keys passed in (or derived from hub objects)

Anything a specific test does need to pin (a plural source table, a composite
business key, a confidence level) is an explicit keyword override.
"""

from __future__ import annotations

from collections.abc import Sequence

from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)

_HUB_PREFIX = "hub_"
_LINK_PREFIX = "link_"


def _bare(name: str, prefix: str) -> str:
    return name[len(prefix):] if name.startswith(prefix) else name


def hash_key_for(name: str, *, prefix: str = _HUB_PREFIX) -> str:
    """The hash-key column a given entity name maps to (single source of truth)."""
    return f"HK_{_bare(name, prefix).upper()}"


def hub(
    name: str,
    *,
    source_table: str | None = None,
    business_keys: Sequence[str] = ("mrid",),
    confidence: DecisionConfidence = DecisionConfidence.HIGH,
) -> HubDecision:
    return HubDecision(
        name=name,
        business_keys=tuple(business_keys),
        source_table=source_table or _bare(name, _HUB_PREFIX),
        hash_key=hash_key_for(name),
        confidence=confidence,
        rationale="t",
    )


def sat(
    name: str,
    parent_hub: str,
    *,
    payload: Sequence[str] = ("col_a",),
    source_table: str | None = None,
    confidence: DecisionConfidence = DecisionConfidence.MEDIUM,
    **extra: object,
) -> SatelliteDecision:
    return SatelliteDecision(
        name=name,
        source_table=source_table or _bare(parent_hub, _HUB_PREFIX),
        parent_hub=parent_hub,
        hash_key=hash_key_for(parent_hub),
        hashdiff=f"HASHDIFF_{name.upper()}",
        payload=tuple(payload),
        confidence=confidence,
        rationale="t",
        **extra,
    )


def link(
    name: str,
    *fk_columns: str,
    source_table: str | None = None,
    confidence: DecisionConfidence = DecisionConfidence.MEDIUM,
) -> LinkDecision:
    return LinkDecision(
        name=name,
        source_table=source_table or _bare(name, _LINK_PREFIX),
        hash_key=hash_key_for(name, prefix=_LINK_PREFIX),
        fk_columns=tuple(fk_columns),
        confidence=confidence,
        rationale="t",
    )


def plan(
    *,
    hubs: Sequence[HubDecision] = (),
    links: Sequence[LinkDecision] = (),
    satellites: Sequence[SatelliteDecision] = (),
    system_id: str = "iec_cim",
) -> ModelingPlan:
    return ModelingPlan(
        system_id=system_id,
        hubs=tuple(hubs),
        links=tuple(links),
        satellites=tuple(satellites),
    )
