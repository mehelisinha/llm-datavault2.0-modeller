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


def _agent_with_cap(
    responses: list[str | None],
    *,
    deployment: str,
    max_tokens: int,
    max_completion_tokens: int,
    samples: int = 1,
) -> tuple[ModellingAgent, _FakeChatCompletions]:
    client = _FakeClient(responses)
    agent = ModellingAgent(
        client=client,  # type: ignore[arg-type]
        deployment=deployment,
        samples=samples,
        max_tokens=max_tokens,
        max_completion_tokens=max_completion_tokens,
    )
    return agent, client.chat.completions


def test_completion_budget_is_clamped_to_model_ceiling_on_retry() -> None:
    # gpt-5 empty-response retry would double 16384 -> 32768; the clamp must
    # hold it at the 16384 model ceiling so Azure never returns HTTP 400.
    agent, calls = _agent_with_cap(
        ["", _valid_plan_json()],
        deployment="gpt-5",
        max_tokens=16384,
        max_completion_tokens=16384,
    )
    plan = agent.propose(_payload())
    assert plan.entity_count == 2
    assert calls.calls[0]["max_completion_tokens"] == 16384
    # Doubled budget (32768) clamped back to the ceiling, not sent raw.
    assert calls.calls[1]["max_completion_tokens"] == 16384


def test_truncated_json_at_ceiling_skips_retry() -> None:
    # Budget already at the ceiling: a truncated-JSON retry would re-truncate
    # identically, so the sample is dropped without a second (wasted) call.
    agent, calls = _agent_with_cap(
        ['{"system_id": "iec_cim", "hubs": ['],  # truncated JSON
        deployment="gpt-4o",
        max_tokens=16384,
        max_completion_tokens=16384,
    )
    with pytest.raises(ModellingAgentError, match="no retry headroom"):
        agent.propose(_payload())
    assert len(calls.calls) == 1


def _two_table_payload() -> DiscoveryPayload:
    def _tbl(name: str) -> SourceTable:
        return SourceTable(
            name=name,
            columns=(
                SourceColumn(
                    name="mrid",
                    raw_dtype="varchar(64)",
                    inferred_type=InferredType.STRING,
                    nullable=False,
                ),
            ),
        )

    return DiscoveryPayload(
        system=SourceSystem(system_id="iec_cim", system_name="IEC CIM", source_type="delta"),
        tables=(_tbl("conducting_equipment"), _tbl("terminal")),
    )


def test_adaptive_split_recovers_when_full_batch_truncates() -> None:
    # Full 2-table batch truncates (no headroom -> dropped, no valid plan);
    # the adaptive split retries each half, both succeed, and merge.
    agent, calls = _agent_with_cap(
        ['{"system_id": "iec_cim", "hubs": [', _valid_plan_json(), _valid_plan_json()],
        deployment="gpt-4o",
        max_tokens=16384,
        max_completion_tokens=16384,
    )
    plan = agent.propose(_two_table_payload())
    assert plan.entity_count == 2  # merged (deduped) result is valid
    # 1 failed full-batch call + 2 half-batch calls.
    assert len(calls.calls) == 3


def test_chunk_tables_balances_instead_of_leaving_singleton() -> None:
    from dbt_builder.src.ai.agents.modeller import _chunk_tables

    def _tbl(i: int) -> SourceTable:
        return SourceTable(
            name=f"t{i}",
            columns=(
                SourceColumn(
                    name="mrid",
                    raw_dtype="varchar(64)",
                    inferred_type=InferredType.STRING,
                    nullable=False,
                ),
            ),
        )

    tables = tuple(_tbl(i) for i in range(9))
    batches = _chunk_tables(tables, max_tables=8, max_prompt_tokens=0)
    sizes = [len(b) for b in batches]
    # Greedy would give [8, 1]; balanced spreads to [5, 4] — no fragile singleton.
    assert sizes == [5, 4]


def test_failed_batch_is_skipped_not_fatal() -> None:
    # Two single-table batches: the first truncates with no headroom (cannot
    # split, cannot recover -> skipped); the second is valid. The run must
    # still succeed on the survivor instead of failing the whole catalogue.
    client = _FakeClient(['{"system_id": "iec_cim", "hubs": [', _valid_plan_json()])
    agent = ModellingAgent(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o",
        samples=1,
        max_tokens=16384,
        max_completion_tokens=16384,
        batch_size=1,
        batch_parallelism=1,
        batch_samples=1,
        sample_parallelism=1,
    )
    plan = agent.propose(_two_table_payload())
    assert plan.entity_count == 2  # only the surviving batch's plan
    assert len(client.chat.completions.calls) == 2


def test_adaptive_split_reraises_for_single_table_truncation() -> None:
    # A single table that still truncates cannot be split further -> surface it.
    agent, _ = _agent_with_cap(
        ['{"system_id": "iec_cim", "hubs": ['],
        deployment="gpt-4o",
        max_tokens=16384,
        max_completion_tokens=16384,
    )
    with pytest.raises(ModellingAgentError, match="no retry headroom"):
        agent.propose(_payload())  # single-table payload


def test_system_prompt_loads_from_rule_file_and_keeps_output_contract() -> None:
    from dbt_builder.src.ai.agents import modeller as m

    sp = m._system_prompt()
    # Rules come from prompts/rv_modelling_rules.md; the JSON output contract is
    # appended in code. Default assembly must equal the built-in fallback so
    # behaviour is unchanged when the file is present.
    assert sp.startswith("You are a senior Data Vault")
    assert sp.rstrip().endswith("outside the JSON object.")
    assert "sys_user_grmember" in sp  # ServiceNow rules present
    assert "mRID" in sp  # CIM rules present
    assert sp == f"{m._BUILTIN_RV_RULES}\n\n{m._OUTPUT_CONTRACT}"


def test_truncated_json_below_ceiling_still_retries() -> None:
    # Headroom remains (budget < ceiling) -> the doubled-budget retry runs and
    # can rescue the sample.
    agent, calls = _agent_with_cap(
        ['{"system_id": "iec_cim", "hubs": [', _valid_plan_json()],
        deployment="gpt-4o",
        max_tokens=4096,
        max_completion_tokens=16384,
    )
    plan = agent.propose(_payload())
    assert plan.entity_count == 2
    assert len(calls.calls) == 2
    assert calls.calls[1]["max_tokens"] == 8192
