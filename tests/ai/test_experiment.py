"""Phase 6: experiment harness — per-plan metric bundle + ablation runner."""

from __future__ import annotations

from dbt_builder.src.ai.contracts.decisions import HubDecision, ModelingPlan, SatelliteDecision
from dbt_builder.src.ai.evaluation import (
    AblationArm,
    ExperimentCase,
    GoldModel,
    aggregate,
    evaluate_plan,
    run_ablation,
)


def _sat(name, parent):
    return SatelliteDecision(
        name=name,
        source_table="t",
        parent_hub=parent,
        hash_key="HK_T",
        hashdiff="HD_T",
        payload=("d",),
    )


def _clean_plan(name="hub_user", bk="user_name") -> ModelingPlan:
    return ModelingPlan(
        system_id="t",
        hubs=(HubDecision(name=name, source_table="t", business_keys=(bk,), hash_key="HK_T"),),
        satellites=(_sat("sat_user_details", name),),
    )


def _messy_plan() -> ModelingPlan:
    # bad prefix + surrogate key + no satellite -> multiple conformance issues
    return ModelingPlan(
        system_id="t",
        hubs=(HubDecision(name="user", source_table="t", business_keys=("id",), hash_key="X"),),
    )


def test_evaluate_plan_populates_gold_fields_when_gold_present():
    gold = GoldModel(
        system_id="t", hubs={"hub_user": ("user_name",)}, satellites=("sat_user_details",)
    )
    m = evaluate_plan(_clean_plan(), source_tables=("t",), gold=gold)
    assert m.conformance_score == 1.0
    assert m.gold_macro_f1 is not None
    assert m.gold_bk_accuracy == 1.0
    assert m.coverage_ratio == 1.0


def test_evaluate_plan_gold_fields_none_without_gold():
    m = evaluate_plan(_clean_plan(), source_tables=("t",))
    assert m.gold_macro_f1 is None


def test_aggregate_means_scalars():
    ms = [evaluate_plan(_clean_plan()), evaluate_plan(_messy_plan())]
    agg = aggregate(ms)
    assert agg["n_cases"] == 2.0
    # clean scores 1.0, messy < 1.0 -> mean strictly between
    assert 0.0 < agg["conformance_score"] < 1.0


def test_run_ablation_contrasts_arms():
    # Simulate the study: OFF arm returns a messy plan, ON arm a clean one.
    cases = [ExperimentCase(system_id="t", source_tables=("t",))]

    def propose(arm: AblationArm, case: ExperimentCase) -> ModelingPlan:
        return _clean_plan() if arm.config.get("learning") else _messy_plan()

    arms = [
        AblationArm(label="learning_off", config={"learning": False}),
        AblationArm(label="learning_on", config={"learning": True}),
    ]
    results = run_ablation(cases, propose=propose, arms=arms)
    assert set(results) == {"learning_off", "learning_on"}
    # learning ON should have a higher mean conformance score than OFF
    assert (
        results["learning_on"]["conformance_score"] > results["learning_off"]["conformance_score"]
    )
    # and fewer weighted errors
    assert (
        results["learning_on"]["weighted_error_impact"]
        < results["learning_off"]["weighted_error_impact"]
    )


def test_aggregate_empty_is_empty():
    assert aggregate([]) == {}
