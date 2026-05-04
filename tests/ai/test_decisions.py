"""Unit tests for ai.contracts.decisions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    EntityKind,
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)


def _hub(name: str = "hub_x") -> HubDecision:
    return HubDecision(
        name=name,
        source_table="x",
        business_keys=("mrid",),
        hash_key="HK_X",
        confidence=DecisionConfidence.HIGH,
    )


def test_hub_kind_is_immutable_and_correct():
    hub = _hub()
    assert hub.kind is EntityKind.HUB


def test_satellite_requires_known_parent_hub():
    hub = _hub("hub_a")
    sat = SatelliteDecision(
        name="sat_a_details",
        source_table="x",
        parent_hub="hub_a",
        hash_key="HK_A",
        hashdiff="HD_A",
        payload=("name",),
    )
    plan = ModelingPlan(system_id="S", hubs=(hub,), satellites=(sat,))
    assert plan.entity_count == 2


def test_satellite_with_unknown_parent_hub_fails_plan_validation():
    hub = _hub("hub_a")
    sat = SatelliteDecision(
        name="sat_orphan",
        source_table="x",
        parent_hub="hub_does_not_exist",
        hash_key="HK_X",
        hashdiff="HD_X",
        payload=("name",),
    )
    with pytest.raises(ValidationError):
        ModelingPlan(system_id="S", hubs=(hub,), satellites=(sat,))


def test_plan_rejects_duplicate_hub_names():
    with pytest.raises(ValidationError):
        ModelingPlan(system_id="S", hubs=(_hub("h"), _hub("h")))


def test_plan_rejects_name_collision_across_kinds():
    hub = _hub("shared_name")
    link = LinkDecision(
        name="shared_name",
        source_table="x",
        hash_key="HK_L",
        fk_columns=("HK_A", "HK_B"),
    )
    with pytest.raises(ValidationError):
        ModelingPlan(system_id="S", hubs=(hub,), links=(link,))


def test_link_requires_at_least_two_fks():
    with pytest.raises(ValidationError):
        LinkDecision(name="lnk", source_table="x", hash_key="HK", fk_columns=("HK_A",))


def test_rationale_is_capped():
    with pytest.raises(ValidationError):
        HubDecision(
            name="h",
            source_table="x",
            business_keys=("mrid",),
            hash_key="HK_X",
            rationale="x" * 2001,
        )
