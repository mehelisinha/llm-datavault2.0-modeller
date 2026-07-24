"""Approval recommendation — verdict + reasons from the objective checks. Pure."""

from __future__ import annotations

from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.contracts.payloads import (
    DiscoveryPayload,
    SourceColumn,
    SourceSystem,
    SourceTable,
)
from dbt_builder.src.ai.evaluation.conformance import score_plan
from dbt_builder.src.ai.evaluation.gold import GoldHub, GoldModel, grade_against_gold
from dbt_builder.src.ai.evaluation.grounding import check_grounding
from dbt_builder.src.ai.evaluation.recommend import ApprovalVerdict, recommend_approval


def _payload() -> DiscoveryPayload:
    return DiscoveryPayload(
        system=SourceSystem(system_id="s", system_name="S"),
        tables=(SourceTable(name="terminals", columns=(
            SourceColumn(name="mrid", raw_dtype="string"),
            SourceColumn(name="name", raw_dtype="string"),
        )),),
    )


def _gold() -> GoldModel:
    return GoldModel(system_id="s", hubs=(
        GoldHub(source_table="terminals", business_keys=("mrid",), name="hub_terminal"),),
        links=(), satellites=("sat_terminal",))


def _clean_plan() -> ModelingPlan:
    return ModelingPlan(system_id="s", hubs=(
        HubDecision(name="hub_terminal", source_table="terminals",
                    business_keys=("mrid",), hash_key="HK_TERMINAL"),),
        satellites=(SatelliteDecision(name="sat_terminal", source_table="terminals",
                    parent_hub="hub_terminal", hash_key="HK_TERMINAL",
                    hashdiff="HD_TERMINAL", payload=("name",)),))


def _rec(plan, *, with_gold=True, with_payload=True):
    return recommend_approval(
        conformance=score_plan(plan),
        grounding=check_grounding(plan, _payload()) if with_payload else None,
        gold=grade_against_gold(plan, _gold()) if with_gold else None,
    )


# ── APPROVE ──────────────────────────────────────────────────────────────────


def test_clean_plan_is_approved():
    rec = _rec(_clean_plan())
    assert rec.verdict is ApprovalVerdict.APPROVE
    assert rec.blocking_reasons == () and rec.review_reasons == ()


# ── REJECT (structural defects) ──────────────────────────────────────────────


def test_fabricated_business_key_is_rejected():
    # A business key that is not a real source column breaks the hub's identity.
    plan = ModelingPlan(system_id="s", hubs=(
        HubDecision(name="hub_terminal", source_table="terminals",
                    business_keys=("ghost_key",), hash_key="HK_T"),),
        satellites=(SatelliteDecision(name="sat_t", source_table="terminals",
                    parent_hub="hub_terminal", hash_key="HK_T", hashdiff="HD_T",
                    payload=("name",)),))
    rec = _rec(plan, with_gold=False)
    assert rec.verdict is ApprovalVerdict.REJECT
    assert any("ghost_key" in r for r in rec.blocking_reasons)


def test_fabricated_table_is_rejected():
    # The whole source table is invented — the object has no real origin.
    plan = ModelingPlan(system_id="s", hubs=(
        HubDecision(name="hub_ghost", source_table="nonexistent_table",
                    business_keys=("mrid",), hash_key="HK_G"),),
        satellites=(SatelliteDecision(name="sat_g", source_table="nonexistent_table",
                    parent_hub="hub_ghost", hash_key="HK_G", hashdiff="HD_G",
                    payload=("name",)),))
    rec = _rec(plan, with_gold=False)
    assert rec.verdict is ApprovalVerdict.REJECT
    assert any("nonexistent_table" in r for r in rec.blocking_reasons)


def test_empty_plan_is_rejected():
    rec = _rec(ModelingPlan(system_id="s"))
    assert rec.verdict is ApprovalVerdict.REJECT
    assert any("no hubs" in r for r in rec.blocking_reasons)


# ── REVIEW (localized, fixable — no longer a hard REJECT) ─────────────────────


def test_fabricated_payload_column_is_review_not_reject():
    # One stray descriptive column on an otherwise-sound satellite: fixable by
    # dropping it, so it must fall to REVIEW rather than force a blanket REJECT.
    plan = ModelingPlan(system_id="s", hubs=(
        HubDecision(name="hub_terminal", source_table="terminals",
                    business_keys=("mrid",), hash_key="HK_T"),),
        satellites=(SatelliteDecision(name="sat_t", source_table="terminals",
                    parent_hub="hub_terminal", hash_key="HK_T", hashdiff="HD_T",
                    payload=("ghost_column",)),))
    rec = _rec(plan, with_gold=False)
    assert rec.verdict is ApprovalVerdict.REVIEW
    assert rec.blocking_reasons == ()
    assert any("ghost_column" in r for r in rec.review_reasons)


# ── REVIEW (imperfect, human decides) ────────────────────────────────────────


def test_missed_entity_is_review():
    # gold expects a terminals hub; produce a different (spurious) entity instead.
    plan = ModelingPlan(system_id="s", hubs=(
        HubDecision(name="hub_other", source_table="terminals", business_keys=("name",),
                    hash_key="HK_O"),),
        satellites=(SatelliteDecision(name="sat_o", source_table="terminals",
                    parent_hub="hub_other", hash_key="HK_O", hashdiff="HD_O",
                    payload=("mrid",)),))
    rec = _rec(plan)
    assert rec.verdict is ApprovalVerdict.REVIEW
    assert any("missed" in r for r in rec.review_reasons)
    assert any("not in the reference" in r for r in rec.review_reasons)


def test_naming_gap_is_review():
    plan = ModelingPlan(system_id="s", hubs=(
        HubDecision(name="hub_terminals", source_table="terminals",  # plural != gold
                    business_keys=("mrid",), hash_key="HK_T"),),
        satellites=(SatelliteDecision(name="sat_t", source_table="terminals",
                    parent_hub="hub_terminals", hash_key="HK_T", hashdiff="HD_T",
                    payload=("name",)),))
    rec = _rec(plan)
    assert rec.verdict is ApprovalVerdict.REVIEW
    assert any("naming convention not followed" in r for r in rec.review_reasons)


def test_no_gold_cannot_rise_above_review():
    # A structurally clean plan, but no reference model -> correctness unverifiable.
    rec = _rec(_clean_plan(), with_gold=False)
    assert rec.verdict is ApprovalVerdict.REVIEW
    assert any("no reference model" in r for r in rec.review_reasons)


def test_rejection_message_is_meaningful_and_joined():
    rec = _rec(ModelingPlan(system_id="s"))
    assert rec.rejection_message  # non-empty, human readable
    assert ";" in rec.rejection_message or "no hubs" in rec.rejection_message
