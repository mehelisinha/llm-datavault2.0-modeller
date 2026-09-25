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
    responses: list[str | None],
    *,
    deployment: str = "gpt-4o",
    samples: int = 1,
    technical_payload_columns: frozenset[str] = frozenset(),
) -> tuple[ModellingAgent, _FakeChatCompletions]:
    client = _FakeClient(responses)
    agent = ModellingAgent(
        client=client,  # type: ignore[arg-type]
        deployment=deployment,
        samples=samples,
        max_tokens=512,
        technical_payload_columns=technical_payload_columns,
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


def test_verbose_model_output_is_coerced_to_strict_schema() -> None:
    # gpt-4.1-style reply: extra keys, a `business_key` (singular) alias, a
    # `columns` alias for payload, and 4 satellites on one hub (over the cap).
    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "domain_context": "should be ignored",  # extra top-level key
            "hubs": [
                {
                    "name": "hub_ce",
                    "source_table": "conducting_equipment",
                    "business_key": "mrid",  # singular alias
                    "hash_key": "HK_CE",
                    "confidence": "HIGH",  # wrong case
                    "description": "extra key",  # forbidden key
                    "kind": "hub",  # dropped; default applies
                }
            ],
            "links": [],
            "satellites": [
                {
                    "name": "sat_ce_a",
                    "source_table": "conducting_equipment",
                    "parent_hub": "hub_ce",
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_A",
                    "columns": ["c1"],  # alias for payload
                    "note": "extra",
                },
                *[
                    {
                        "name": f"sat_ce_{x}",
                        "source_table": "conducting_equipment",
                        "parent_hub": "hub_ce",
                        "hash_key": "HK_CE",
                        "hashdiff": f"HD_{x}",
                        "payload": [f"c{x}"],
                    }
                    for x in ("b", "c", "d")  # 'd' is the 4th → dropped by cap
                ],
            ],
        }
    )
    agent, _ = _agent([reply], samples=1)
    plan = agent.propose(_payload())
    assert len(plan.hubs) == 1
    assert plan.hubs[0].business_keys == ("mrid",)
    assert len(plan.satellites) == 3  # 4th satellite dropped at the per-hub cap


def test_invalid_satellites_are_dropped_not_fatal() -> None:
    # gpt-4.1 mixes one good satellite with three the contract would reject:
    # empty payload, a non-string parent_hub, and an invented eff_sat whose
    # parent is a link. Coercion must drop only the bad ones so the rest of the
    # plan still validates (previously one bad sat failed the whole batch).
    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": "hub_ce",
                    "source_table": "conducting_equipment",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_CE",
                }
            ],
            "links": [],
            "satellites": [
                {
                    "name": "sat_ce_good",
                    "source_table": "conducting_equipment",
                    "parent_hub": "hub_ce",
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_GOOD",
                    "payload": ["name"],
                },
                {  # empty payload -> dropped
                    "name": "sat_ce_empty",
                    "source_table": "conducting_equipment",
                    "parent_hub": "hub_ce",
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_EMPTY",
                    "payload": [],
                },
                {  # non-string parent_hub -> dropped
                    "name": "sat_ce_badparent",
                    "source_table": "conducting_equipment",
                    "parent_hub": ["hub_ce"],
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_BAD",
                    "payload": ["name"],
                },
                {  # eff_sat invented as a sat pointing at a link -> dropped
                    "name": "eff_sat_ce",
                    "source_table": "conducting_equipment",
                    "parent_hub": "link_ce_node",
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_EFF",
                    "payload": ["name"],
                },
            ],
        }
    )
    agent, _ = _agent([reply], samples=1)
    plan = agent.propose(_payload())
    assert len(plan.hubs) == 1
    assert [s.name for s in plan.satellites] == ["sat_ce_good"]


def test_duplicate_hub_names_are_merged_not_fatal() -> None:
    # Large batched catalogs make gpt-4.1 propose the same hub twice — e.g. a
    # PII and a non-PII view of one entity both yield "hub_ce" (with different
    # business keys). The contract forbids duplicate hub names, so coercion must
    # MERGE them (union business keys) rather than fail the whole batch.
    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": "hub_ce",
                    "source_table": "conducting_equipment",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_CE",
                },
                {
                    "name": "hub_ce",
                    "source_table": "conducting_equipment_nonpii",
                    "business_keys": ["name"],
                    "hash_key": "HK_CE",
                },
            ],
            "links": [],
            "satellites": [],
        }
    )
    agent, _ = _agent([reply], samples=1)
    plan = agent.propose(_payload())
    assert len(plan.hubs) == 1
    # Both business keys are preserved (first-occurrence order), nothing dropped.
    assert plan.hubs[0].business_keys == ("mrid", "name")


def test_duplicate_link_names_are_merged_not_fatal() -> None:
    # PII/non-PII variants emit the same link twice (with overlapping FKs). The
    # contract forbids duplicate names, so coercion merges them (union fk columns)
    # instead of failing the batch.
    fks_a = ["HK_CE", "HK_OTHER"]
    fks_b = ["HK_CE", "HK_THIRD"]
    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": "hub_ce",
                    "source_table": "conducting_equipment",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_CE",
                },
                # The merged link's FK hubs must exist, else the deterministic
                # link-parsimony pass (correctly) prunes it as an unresolved link.
                {
                    "name": "hub_other",
                    "source_table": "other",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_OTHER",
                },
                {
                    "name": "hub_third",
                    "source_table": "third",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_THIRD",
                },
            ],
            "links": [
                {
                    "name": "link_ce_rel",
                    "source_table": "conducting_equipment",
                    "hash_key": "HK_LINK_CE_REL",
                    "fk_columns": fks_a,
                },
                {
                    "name": "link_ce_rel",
                    "source_table": "conducting_equipment",
                    "hash_key": "HK_LINK_CE_REL",
                    "fk_columns": fks_b,
                },
            ],
            "satellites": [],
        }
    )
    agent, _ = _agent([reply], samples=1)
    plan = agent.propose(_payload())
    assert len(plan.links) == 1
    merged = plan.links[0].fk_columns
    assert set(merged) == set(fks_a) | set(fks_b)  # every FK preserved
    assert len(merged) == len(set(merged))  # no duplicates re-introduced


def test_duplicate_satellite_names_are_merged_not_fatal() -> None:
    # The same satellite proposed twice (different payload columns) is merged by
    # unioning its payload rather than colliding on its name.
    pay_a = ["name"]
    pay_b = ["description"]
    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": "hub_ce",
                    "source_table": "conducting_equipment",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_CE",
                }
            ],
            "links": [],
            "satellites": [
                {
                    "name": "sat_ce_all",
                    "source_table": "conducting_equipment",
                    "parent_hub": "hub_ce",
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_CE_ALL",
                    "payload": pay_a,
                },
                {
                    "name": "sat_ce_all",
                    "source_table": "conducting_equipment",
                    "parent_hub": "hub_ce",
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_CE_ALL",
                    "payload": pay_b,
                },
            ],
        }
    )
    agent, _ = _agent([reply], samples=1)
    plan = agent.propose(_payload())
    assert len(plan.satellites) == 1
    merged = plan.satellites[0].payload
    assert set(merged) == set(pay_a) | set(pay_b)
    assert len(merged) == len(set(merged))


def test_cross_type_name_collision_is_resolved() -> None:
    # A link and a satellite that reuse a hub's name violate the "names unique
    # across hubs / links / satellites" invariant. Coercion keeps the hub (the
    # anchor) and drops the colliding entities so the rest of the plan survives.
    clashing = "hub_ce"
    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": clashing,
                    "source_table": "conducting_equipment",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_CE",
                }
            ],
            "links": [
                {
                    "name": clashing,
                    "source_table": "conducting_equipment",
                    "hash_key": "HK_LINK_CE",
                    "fk_columns": ["HK_CE", "HK_X"],
                }
            ],
            "satellites": [
                {
                    "name": clashing,
                    "source_table": "conducting_equipment",
                    "parent_hub": clashing,
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_CE",
                    "payload": ["name"],
                }
            ],
        }
    )
    agent, _ = _agent([reply], samples=1)
    plan = agent.propose(_payload())
    assert {h.name for h in plan.hubs} == {clashing}
    assert plan.links == ()  # link reusing the hub name dropped
    assert plan.satellites == ()  # sat reusing the hub name dropped


def test_foreign_and_business_keys_are_stripped_from_satellite_payload() -> None:
    # A satellite payload that includes its own hub's business key and a foreign
    # key (another hub's business key, established by a link on the same source
    # table) must be cleaned: keys live in hubs / links, never in a descriptive
    # hashdiff. Descriptive columns survive in order.
    own_bk = "mrid"
    foreign_bk = "owner_id"
    descriptive = ["name", "status"]
    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": "hub_ce",
                    "source_table": "conducting_equipment",
                    "business_keys": [own_bk],
                    "hash_key": "HK_CE",
                },
                {
                    "name": "hub_owner",
                    "source_table": "conducting_equipment",
                    "business_keys": [foreign_bk],
                    "hash_key": "HK_OWNER",
                },
            ],
            "links": [
                {
                    "name": "link_ce_owner",
                    "source_table": "conducting_equipment",
                    "hash_key": "HK_CE_OWNER",
                    "fk_columns": ["HK_CE", "HK_OWNER"],
                }
            ],
            "satellites": [
                {
                    "name": "sat_ce_all",
                    "source_table": "conducting_equipment",
                    "parent_hub": "hub_ce",
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_CE_ALL",
                    "payload": [own_bk, *descriptive, foreign_bk],
                }
            ],
        }
    )
    agent, _ = _agent([reply], samples=1)
    plan = agent.propose(_payload())
    sat = next(s for s in plan.satellites if s.name == "sat_ce_all")
    assert list(sat.payload) == descriptive  # own BK + FK removed, order preserved


def test_generic_descriptive_column_is_not_stripped_as_a_foreign_key() -> None:
    # `name` is hub_country's business key, but for an UNRELATED hub's satellite
    # (no link joining them on this table) it is a legitimate descriptive column
    # and must be preserved — FK stripping is scoped to links, not global.
    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": "hub_country",
                    "source_table": "country",
                    "business_keys": ["name"],
                    "hash_key": "HK_COUNTRY",
                },
                {
                    "name": "hub_ce",
                    "source_table": "conducting_equipment",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_CE",
                },
            ],
            "links": [],
            "satellites": [
                {
                    "name": "sat_ce_all",
                    "source_table": "conducting_equipment",
                    "parent_hub": "hub_ce",
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_CE_ALL",
                    "payload": ["name", "status"],
                }
            ],
        }
    )
    agent, _ = _agent([reply], samples=1)
    plan = agent.propose(_payload())
    sat = next(s for s in plan.satellites if s.name == "sat_ce_all")
    assert list(sat.payload) == ["name", "status"]  # `name` kept — not a FK here


def test_technical_columns_are_stripped_from_satellite_payload() -> None:
    # Caller-configured technical/system columns are removed case-insensitively;
    # the agent sources the list from settings (empty by default, source-agnostic).
    technical = frozenset({"ctl_load_flag", "audit_user"})
    descriptive = ["name"]
    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": "hub_ce",
                    "source_table": "conducting_equipment",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_CE",
                }
            ],
            "links": [],
            "satellites": [
                {
                    "name": "sat_ce_all",
                    "source_table": "conducting_equipment",
                    "parent_hub": "hub_ce",
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_CE_ALL",
                    "payload": ["CTL_LOAD_FLAG", *descriptive, "Audit_User"],
                }
            ],
        }
    )
    agent, _ = _agent([reply], samples=1, technical_payload_columns=technical)
    plan = agent.propose(_payload())
    sat = next(s for s in plan.satellites if s.name == "sat_ce_all")
    assert list(sat.payload) == descriptive


def test_satellite_with_only_keys_and_technical_is_dropped() -> None:
    # If cleaning removes every column, the satellite has nothing to track and
    # is dropped rather than emitted with an empty (invalid) payload.
    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": "hub_ce",
                    "source_table": "conducting_equipment",
                    "business_keys": ["mrid"],
                    "hash_key": "HK_CE",
                }
            ],
            "links": [],
            "satellites": [
                {
                    "name": "sat_ce_keyonly",
                    "source_table": "conducting_equipment",
                    "parent_hub": "hub_ce",
                    "hash_key": "HK_CE",
                    "hashdiff": "HD_CE",
                    "payload": ["mrid"],  # only the business key — nothing descriptive
                }
            ],
        }
    )
    agent, _ = _agent([reply], samples=1)
    plan = agent.propose(_payload())
    assert all(s.name != "sat_ce_keyonly" for s in plan.satellites)


def test_split_satellites_get_subgroup_and_matching_velocity_derived() -> None:
    # A rate-of-change split is encoded in the satellite name suffix; coercion
    # derives the audit metadata (subgroup + the velocity that follows it) when
    # the model omits it. Unsplit satellites keep their honest default velocity.
    from dbt_builder.src.ai.agents.modeller import _VELOCITY_BY_SUBGROUP
    from dbt_builder.src.ai.contracts.decisions import SatelliteDecision

    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {"name": "hub_x", "source_table": "tx", "business_keys": ["code"], "hash_key": "HK_X"},
                {"name": "hub_y", "source_table": "ty", "business_keys": ["ykey"], "hash_key": "HK_Y"},
            ],
            "links": [],
            "satellites": [
                {"name": "sat_x_details", "source_table": "tx", "parent_hub": "hub_x", "hash_key": "HK_X", "hashdiff": "HD_X_D", "payload": ["name"]},
                {"name": "sat_x_operational", "source_table": "tx", "parent_hub": "hub_x", "hash_key": "HK_X", "hashdiff": "HD_X_O", "payload": ["status"]},
                {"name": "sat_y_all", "source_table": "ty", "parent_hub": "hub_y", "hash_key": "HK_Y", "hashdiff": "HD_Y", "payload": ["label"]},
            ],
        }
    )
    agent, _ = _agent([reply], samples=1)
    plan = agent.propose(_payload())
    by_name = {s.name: s for s in plan.satellites}

    for name in ("sat_x_details", "sat_x_operational"):
        suffix = name.rsplit("_", 1)[-1]  # the split subgroup the name encodes
        assert by_name[name].subgroup == suffix
        assert by_name[name].change_velocity == _VELOCITY_BY_SUBGROUP[suffix]

    # Unsplit satellite: no subgroup, contract-default velocity preserved.
    default_velocity = SatelliteDecision.model_fields["change_velocity"].default
    assert by_name["sat_y_all"].subgroup is None
    assert by_name["sat_y_all"].change_velocity == default_velocity


def test_link_with_too_few_fk_columns_is_dropped_not_fatal() -> None:
    # A link relating fewer hubs than the contract minimum is malformed; coercion
    # drops just that link instead of failing (and skipping) the whole batch.
    reply = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {"name": "hub_ce", "source_table": "conducting_equipment", "business_keys": ["mrid"], "hash_key": "HK_CE"},
                {"name": "hub_node", "source_table": "conducting_equipment", "business_keys": ["nid"], "hash_key": "HK_NODE"},
            ],
            "links": [
                {"name": "link_good", "source_table": "conducting_equipment", "hash_key": "HK_GOOD", "fk_columns": ["HK_CE", "HK_NODE"]},
                {"name": "link_bad", "source_table": "conducting_equipment", "hash_key": "HK_BAD", "fk_columns": ["HK_CE"]},
            ],
            "satellites": [],
        }
    )
    agent, _ = _agent([reply], samples=1)
    plan = agent.propose(_payload())
    names = {ln.name for ln in plan.links}
    assert "link_good" in names
    assert "link_bad" not in names  # one-FK link dropped, batch survives


def test_schema_invalid_does_not_trigger_adaptive_split() -> None:
    # A full but malformed plan (hub missing hash_key) — splitting can't fix it,
    # so the agent must fail fast (one round of calls), not recurse.
    bad = json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [{"name": "hub_x", "source_table": "t", "business_keys": ["mrid"]}],
            "links": [],
            "satellites": [],
        }
    )
    agent, calls = _agent([bad, bad, bad], samples=1)
    with pytest.raises(ModellingAgentError, match="schema invalid"):
        agent.propose(_two_table_payload())
    assert len(calls.calls) == 1  # one sample, no wasteful split retries


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
