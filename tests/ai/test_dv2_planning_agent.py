"""Tests for the opt-in DV2 Planning Agent (offline)."""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.ai

from dbt_builder.src.ai.agents.dv2_planning_agent import (  # noqa: E402
    Dv2Plan,
    Dv2PlanningAgent,
    Dv2PlanningAgentError,
)
from dbt_builder.src.ai.settings import AISettings  # noqa: E402

from .test_modeller import _FakeClient, _payload  # noqa: E402


def test_system_prompt_loads_rules_from_file_and_keeps_schema_contract() -> None:
    from dbt_builder.src.ai.agents import dv2_planning_agent as m

    sp = m._system_prompt()
    # Schema contract (fixed in code) must be present and match Dv2Plan fields.
    assert "hub_decisions" in sp
    assert "pit_volume_estimates" in sp
    # Decision rules loaded from planning_rules.md.
    assert "rate-of-change" in sp
    assert "HUB / LINK / REFERENCE / SKIP" in sp


def _settings(*, seed: int = 42) -> AISettings:
    return AISettings(
        azure_openai_endpoint="https://example.invalid",
        azure_openai_api_key="sk-test",  # pyright: ignore[reportArgumentType]
        llm_seed=seed,
        planning_agent_enabled=True,
    )


_VALID_REPLY = json.dumps(
    {
        "system_id": "WRONG",  # overridden by payload
        "hub_decisions": [
            {
                "table": "conducting_equipment",
                "business_keys": ["mrid"],
                "confidence": "high",
                "rationale": "Stable CIM identifier.",
            }
        ],
        "link_decisions": [],
        "satellite_splits": [
            {
                "parent_hub": "hub_conducting_equipment",
                "sat_name": "sat_ce_descriptive",
                "columns": ["name"],
                "rationale": "Slowly-changing descriptive attributes.",
            }
        ],
        "reference_tables": [],
        "bv_proposals": [],
        "pit_volume_estimates": [],
        "edge_cases": [],
        "review_flags": [],
    }
)


def test_plan_returns_validated_document() -> None:
    client = _FakeClient([_VALID_REPLY])
    agent = Dv2PlanningAgent(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o",
        settings=_settings(),
        max_tokens=512,
    )
    plan = agent.plan(_payload())
    assert isinstance(plan, Dv2Plan)
    # system_id is taken from payload, not the model's reply.
    assert plan.system_id == "iec_cim"
    assert plan.hub_decisions[0].table == "conducting_equipment"
    assert plan.satellite_splits[0].sat_name == "sat_ce_descriptive"


def test_plan_passes_seed_when_enabled() -> None:
    client = _FakeClient([_VALID_REPLY])
    agent = Dv2PlanningAgent(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o",
        settings=_settings(seed=11),
        max_tokens=512,
    )
    agent.plan(_payload())
    assert client.chat.completions.calls[0]["seed"] == 11


def test_plan_omits_seed_when_disabled() -> None:
    client = _FakeClient([_VALID_REPLY])
    agent = Dv2PlanningAgent(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o",
        settings=_settings(seed=-1),
        max_tokens=512,
    )
    agent.plan(_payload())
    assert "seed" not in client.chat.completions.calls[0]


def test_invalid_json_raises() -> None:
    client = _FakeClient(["not json"])
    agent = Dv2PlanningAgent(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o",
        settings=_settings(),
        max_tokens=512,
    )
    with pytest.raises(Dv2PlanningAgentError, match="not JSON"):
        agent.plan(_payload())


def test_schema_violation_raises() -> None:
    # Missing required system_id field — actually overridden by payload,
    # so test a field type violation instead: business_keys must be list[str].
    bad = json.dumps(
        {
            "system_id": "iec_cim",
            "hub_decisions": [
                {
                    "table": "conducting_equipment",
                    "business_keys": "mrid",  # should be a list
                    "confidence": "high",
                    "rationale": "",
                }
            ],
            "link_decisions": [],
            "satellite_splits": [],
            "reference_tables": [],
            "bv_proposals": [],
            "pit_volume_estimates": [],
            "edge_cases": [],
            "review_flags": [],
        }
    )
    client = _FakeClient([bad])
    agent = Dv2PlanningAgent(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o",
        settings=_settings(),
        max_tokens=512,
    )
    with pytest.raises(Dv2PlanningAgentError, match="schema validation"):
        agent.plan(_payload())


def test_empty_reply_raises() -> None:
    client = _FakeClient([""])
    agent = Dv2PlanningAgent(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o",
        settings=_settings(),
        max_tokens=512,
    )
    with pytest.raises(Dv2PlanningAgentError, match="empty completion"):
        agent.plan(_payload())
