"""Tests for the LLM modelling agent (offline; live tests in commit #6)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

pytestmark = pytest.mark.ai

from dbt_builder.src.ai.agents.modeller import (  # noqa: E402
    ModellingAgent,
    ModellingAgentError,
)
from dbt_builder.src.ai.contracts.payloads import (  # noqa: E402
    DiscoveryPayload,
    InferredType,
    SourceColumn,
    SourceSystem,
    SourceTable,
)

# --------------------------------------------------------------------- fixtures


def _payload() -> DiscoveryPayload:
    return DiscoveryPayload(
        system=SourceSystem(
            system_id="iec_cim",
            system_name="IEC CIM",
            source_type="delta",
        ),
        tables=(
            SourceTable(
                name="conducting_equipment",
                columns=(
                    SourceColumn(
                        name="mrid",
                        raw_dtype="varchar(64)",
                        inferred_type=InferredType.STRING,
                        nullable=False,
                    ),
                    SourceColumn(
                        name="name",
                        raw_dtype="varchar(255)",
                        inferred_type=InferredType.STRING,
                    ),
                ),
            ),
        ),
    )


def _valid_plan_json(*, system_id: str = "iec_cim") -> str:
    return json.dumps(
        {
            "system_id": system_id,
            "hubs": [
                {
                    "name": "hub_conducting_equipment",
                    "source_table": "conducting_equipment",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_CONDUCTING_EQUIPMENT",
                    "confidence": "high",
                    "rationale": "mrid is the standard CIM identifier.",
                }
            ],
            "links": [],
            "satellites": [
                {
                    "name": "sat_conducting_equipment_descriptive",
                    "source_table": "conducting_equipment",
                    "parent_hub": "hub_conducting_equipment",
                    "hash_key": "HK_CONDUCTING_EQUIPMENT",
                    "hashdiff": "HD_CONDUCTING_EQUIPMENT_DESCRIPTIVE",
                    "payload": ["name"],
                    "confidence": "medium",
                    "rationale": "Captures descriptive attributes.",
                }
            ],
        }
    )


def _alt_plan_json() -> str:
    """A second, structurally different valid plan (no satellite)."""
    return json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": "hub_conducting_equipment",
                    "source_table": "conducting_equipment",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_CONDUCTING_EQUIPMENT",
                    "confidence": "low",
                    "rationale": "minimal model",
                }
            ],
            "links": [],
            "satellites": [],
        }
    )


# ----------------------------------------------------------------- fake client


@dataclass
class _FakeChoice:
    message: Any


@dataclass
class _FakeMsg:
    content: str | None


@dataclass
class _FakeCompletion:
    choices: list[_FakeChoice]


class _FakeChatCompletions:
    def __init__(self, responses: list[str | None]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeCompletion:
        self.calls.append(kwargs)
        content = self._responses.pop(0) if self._responses else ""
        return _FakeCompletion(choices=[_FakeChoice(message=_FakeMsg(content=content))])


class _FakeChat:
    def __init__(self, completions: _FakeChatCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, responses: list[str | None]) -> None:
        self.chat = _FakeChat(_FakeChatCompletions(responses))


def _agent(
    responses: list[str | None], *, deployment: str = "gpt-4o", samples: int = 1
) -> tuple[ModellingAgent, _FakeChatCompletions]:
    client = _FakeClient(responses)
    agent = ModellingAgent(
        client=client,  # type: ignore[arg-type]
        deployment=deployment,
        samples=samples,
        max_tokens=512,
    )
    return agent, client.chat.completions


# ----------------------------------------------------------------------- tests


def test_propose_returns_validated_plan() -> None:
    agent, _ = _agent([_valid_plan_json()])
    plan = agent.propose(_payload())
    assert plan.system_id == "iec_cim"
    assert plan.entity_count == 2
    assert plan.hubs[0].name == "hub_conducting_equipment"


def test_system_id_is_overridden_from_payload() -> None:
    # Even if the model invents a different system_id, the payload's wins.
    agent, _ = _agent([_valid_plan_json(system_id="WRONG")])
    plan = agent.propose(_payload())
    assert plan.system_id == "iec_cim"


def test_invalid_json_does_not_raise_when_other_samples_succeed() -> None:
    agent, _ = _agent(["not json", _valid_plan_json(), "also not json"], samples=3)
    plan = agent.propose(_payload())
    assert plan.entity_count == 2


def test_majority_vote_picks_dominant_fingerprint() -> None:
    # Two identical valid plans + one structurally different valid plan.
    agent, _ = _agent(
        [_valid_plan_json(), _alt_plan_json(), _valid_plan_json()],
        samples=3,
    )
    plan = agent.propose(_payload())
    # Majority is the 2-entity plan.
    assert plan.entity_count == 2


def test_tie_break_prefers_higher_confidence() -> None:
    agent, _ = _agent([_valid_plan_json(), _alt_plan_json()], samples=2)
    plan = agent.propose(_payload())
    # Tied at 1 vote each; _valid_plan_json has 'high' + 'medium' confidence
    # (weight 5) vs alt's single 'low' (weight 1) -> high-confidence wins.
    assert plan.entity_count == 2


def test_all_samples_invalid_raises() -> None:
    # Each sample fails differently: invalid JSON, schema-invalid (string
    # instead of object), and JSON list at top level.
    agent, _ = _agent(["not json", '"a string"', "[1, 2, 3]"], samples=3)
    with pytest.raises(ModellingAgentError, match="no valid plans"):
        agent.propose(_payload())


def test_gpt5_uses_max_completion_tokens_and_temperature_one() -> None:
    agent, calls = _agent([_valid_plan_json()], deployment="gpt-5", samples=1)
    agent.propose(_payload())
    assert len(calls.calls) == 1
    kwargs = calls.calls[0]
    assert kwargs["temperature"] == 1.0
    assert "max_completion_tokens" in kwargs
    assert "max_tokens" not in kwargs


def test_non_gpt5_uses_max_tokens_and_temperature_zero() -> None:
    agent, calls = _agent([_valid_plan_json()], deployment="gpt-4o", samples=1)
    agent.propose(_payload())
    kwargs = calls.calls[0]
    assert kwargs["temperature"] == 0.0
    assert "max_tokens" in kwargs
    assert "max_completion_tokens" not in kwargs


def test_gpt5_empty_response_retries_with_doubled_budget() -> None:
    agent, calls = _agent(
        ["", _valid_plan_json()],
        deployment="gpt-5",
        samples=1,
    )
    plan = agent.propose(_payload())
    assert plan.entity_count == 2
    assert len(calls.calls) == 2
    first_budget = calls.calls[0]["max_completion_tokens"]
    second_budget = calls.calls[1]["max_completion_tokens"]
    assert second_budget == first_budget * 2


def test_non_gpt5_empty_response_does_not_retry() -> None:
    agent, calls = _agent(["", "", ""], deployment="gpt-4o", samples=1)
    with pytest.raises(ModellingAgentError):
        agent.propose(_payload())
    # Only one call: empty-content retry is gpt-5 specific.
    assert len(calls.calls) == 1
