"""Unit tests for :class:`LlmBvSatProposer`.

Uses a hand-rolled stub Azure OpenAI client so the tests are hermetic
(no network) and validate the pattern-gating + column-reference
guardrail that protects against LLM hallucination.
"""

from __future__ import annotations

import json
from typing import Any

from dbt_builder.src.ai.agents.bv_sat_proposer import LlmBvSatProposer
from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    HubDecision,
    ModelingPlan,
    SatelliteDecision,
)


def test_system_prompt_loads_rules_from_file_and_keeps_decisions_contract() -> None:
    from dbt_builder.src.ai.agents import bv_sat_proposer as m

    sp = m._system_prompt()
    # Domain rules loaded from bv_sat_proposer_rules.md (incl. skill patterns).
    assert sp.startswith("You are a senior")
    assert "voltage_tier" in sp  # CIM BV pattern from the skill
    # Strict-JSON response contract kept in code.
    assert '"decisions"' in sp
    assert "pattern_key" in sp


# ── stub OpenAI client ──────────────────────────────────────────────────────


class _StubMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _StubChoice:
    def __init__(self, content: str) -> None:
        self.message = _StubMessage(content)


class _StubResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_StubChoice(content)]


class _StubCompletions:
    def __init__(self, payload: str | Exception) -> None:
        self._payload = payload
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _StubResponse:
        self.calls.append(kwargs)
        if isinstance(self._payload, Exception):
            raise self._payload
        return _StubResponse(self._payload)


class _StubChat:
    def __init__(self, payload: str | Exception) -> None:
        self.completions = _StubCompletions(payload)


class _StubClient:
    def __init__(self, payload: str | Exception) -> None:
        self.chat = _StubChat(payload)


class _StubSettings:
    """Minimal AISettings-compatible shim — proposer only reads the gpt-5 flag via deployment name."""

    llm_seed: int = -1


# ── fixtures ────────────────────────────────────────────────────────────────


def _hub() -> HubDecision:
    return HubDecision(
        name="hub_terminal",
        business_keys=("mrid",),
        source_table="terminal",
        hash_key="HK_TERMINAL",
        confidence=DecisionConfidence.HIGH,
        rationale="t",
    )


def _sat_with_voltage() -> SatelliteDecision:
    return SatelliteDecision(
        name="sat_terminal_details",
        source_table="terminal",
        parent_hub="hub_terminal",
        hash_key="HK_TERMINAL",
        hashdiff="HASHDIFF_SAT_TERMINAL_DETAILS",
        payload=("voltage_kv", "name"),
        confidence=DecisionConfidence.MEDIUM,
        rationale="t",
    )


def _plan() -> ModelingPlan:
    return ModelingPlan(
        system_id="iec_cim",
        hubs=(_hub(),),
        satellites=(_sat_with_voltage(),),
    )


def _proposer(payload: str | Exception) -> tuple[LlmBvSatProposer, _StubClient]:
    client = _StubClient(payload)
    proposer = LlmBvSatProposer(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o-mini",
        settings=_StubSettings(),  # type: ignore[arg-type]
    )
    return proposer, client


# ── tests ──────────────────────────────────────────────────────────────────


def test_zero_candidates_means_no_llm_call() -> None:
    # Plan with no pattern-matching columns -> proposer must short-circuit.
    plan = ModelingPlan(system_id="iec_cim", hubs=(_hub(),))
    proposer, client = _proposer("{}")
    out = proposer.propose(plan, plan.hubs)
    assert out == ()
    assert client.chat.completions.calls == []


def test_accept_verdict_produces_satellite_with_refined_sql() -> None:
    body = json.dumps(
        {
            "decisions": [
                {
                    "pattern_key": "voltage_tier",
                    "decision": "accept",
                    "name": "bv_sat_terminal_voltage_tier",
                    "classification": "classification",
                    "output_columns": ["voltage_tier"],
                    "derivation_sql": "case when voltage_kv >= 132 then 'EHV' else 'LV' end",
                    "rationale": "tightened thresholds for the regional grid",
                }
            ]
        }
    )
    proposer, _ = _proposer(body)
    out = proposer.propose(_plan(), _plan().hubs)
    assert len(out) == 1
    sat = out[0]
    assert sat.name == "bv_sat_terminal_voltage_tier"
    assert sat.parent_hub == "hub_terminal"
    assert any("132" in item.derivation_sql for item in sat.payload if item.derivation_sql)


def test_reject_verdict_drops_candidate() -> None:
    body = json.dumps(
        {"decisions": [{"pattern_key": "voltage_tier", "decision": "reject"}]}
    )
    proposer, _ = _proposer(body)
    assert proposer.propose(_plan(), _plan().hubs) == ()


def test_unknown_column_in_derivation_sql_drops_proposal() -> None:
    body = json.dumps(
        {
            "decisions": [
                {
                    "pattern_key": "voltage_tier",
                    "decision": "accept",
                    "derivation_sql": "case when phantom_col > 0 then 'X' end",
                }
            ]
        }
    )
    proposer, _ = _proposer(body)
    # phantom_col is not in any sat payload — proposer must refuse it.
    assert proposer.propose(_plan(), _plan().hubs) == ()


def test_invalid_json_falls_back_to_deterministic_candidate() -> None:
    proposer, _ = _proposer("not json at all")
    out = proposer.propose(_plan(), _plan().hubs)
    # Deterministic fallback uses the candidate's starter SQL/output cols.
    assert len(out) == 1
    assert out[0].name == "bv_sat_terminal_voltage_tier"


def test_llm_call_exception_falls_back_to_deterministic_candidate() -> None:
    proposer, _ = _proposer(RuntimeError("network down"))
    out = proposer.propose(_plan(), _plan().hubs)
    assert len(out) == 1
    assert out[0].name == "bv_sat_terminal_voltage_tier"


def test_missing_decision_keeps_deterministic_candidate() -> None:
    # LLM returns a valid envelope but no entry for our candidate key.
    body = json.dumps({"decisions": []})
    proposer, _ = _proposer(body)
    out = proposer.propose(_plan(), _plan().hubs)
    assert len(out) == 1


def test_rename_violating_prefix_is_reverted_to_candidate_name() -> None:
    body = json.dumps(
        {
            "decisions": [
                {
                    "pattern_key": "voltage_tier",
                    "decision": "accept",
                    "name": "not_a_bv_sat",  # violates the bv_sat_ prefix
                }
            ]
        }
    )
    proposer, _ = _proposer(body)
    out = proposer.propose(_plan(), _plan().hubs)
    assert out[0].name == "bv_sat_terminal_voltage_tier"
