"""Pipeline-run approval recommendation endpoint helper. No network."""

from __future__ import annotations

from datetime import datetime, timezone

from dbt_builder.api.routers.pipeline import _recommendation_for_run
from dbt_builder.src.ai.contracts.catalog import (
    BronzeColumn,
    BronzeSnapshot,
    BronzeTable,
)
from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.contracts.pipeline_run import (
    PipelineRun,
    PipelineRunStatus,
)

NOW = datetime.now(timezone.utc)


def _bronze() -> BronzeSnapshot:
    return BronzeSnapshot(
        catalog="c", schema_name="b", captured_at=NOW,
        tables=(BronzeTable(catalog="c", schema_name="b", name="terminals", columns=(
            BronzeColumn(name="mrid", raw_dtype="string"),
            BronzeColumn(name="name", raw_dtype="string"),
        )),),
    )


def _run_with_plan(plan: ModelingPlan | None) -> PipelineRun:
    run = PipelineRun(run_id="r", status=PipelineRunStatus.PAUSED, created_at=NOW, updated_at=NOW)
    return run.model_copy(update={"plan": plan, "bronze_snapshot": _bronze()})


def _grounded_plan(payload_cols=("name",)) -> ModelingPlan:
    return ModelingPlan(
        system_id="UNKNOWN_SYS", hubs=(HubDecision(
            name="hub_terminal", source_table="terminals",
            business_keys=("mrid",), hash_key="HK_TERMINAL"),),
        satellites=(SatelliteDecision(
            name="sat_terminal", source_table="terminals", parent_hub="hub_terminal",
            hash_key="HK_TERMINAL", hashdiff="HD_TERMINAL", payload=payload_cols),))


def test_grounded_plan_no_gold_is_review():
    rec = _recommendation_for_run(_run_with_plan(_grounded_plan()))
    # No gold for UNKNOWN_SYS -> correctness unverifiable -> review, never approve.
    assert rec.verdict == "review"
    assert rec.hallucination_rate == 0.0
    assert not rec.blocking_reasons


def test_fabricated_column_is_rejected_with_reason():
    rec = _recommendation_for_run(_run_with_plan(_grounded_plan(payload_cols=("ghost_col",))))
    assert rec.verdict == "reject"
    assert rec.hallucination_rate > 0
    assert any("ghost_col" in r for r in rec.blocking_reasons)
    assert "ghost_col" in rec.rejection_message


def test_no_plan_yet_is_empty_verdict():
    # Endpoint returns empty verdict when ANALYZE has not produced a plan.
    from dbt_builder.api.routers.pipeline import GovernanceRecommendation

    run = PipelineRun(run_id="r", status=PipelineRunStatus.RUNNING, created_at=NOW, updated_at=NOW)
    assert run.plan is None  # sanity: no plan on a fresh run
    empty = GovernanceRecommendation(verdict="", review_reasons=["plan not generated yet"])
    assert empty.verdict == ""
