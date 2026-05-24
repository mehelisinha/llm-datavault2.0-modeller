"""Tests for :class:`PipelineOrchestrator` — end-to-end orchestration of the
five pipeline steps with deterministic stubs for catalog/bronze/LLM.
"""

from __future__ import annotations

from dbt_builder.src.ai.agents import BvArchitect, SchemaAnalyzer, YamlGenerator
from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    HubDecision,
    ModelingPlan,
)
from dbt_builder.src.ai.contracts.payloads import DiscoveryPayload, SourceSystem
from dbt_builder.src.ai.contracts.pipeline_run import (
    PipelineRunStatus,
    PipelineStepName,
    StopAfter,
)
from dbt_builder.src.ai.contracts.supervision import (
    SupervisionRecommendation,
)
from dbt_builder.src.ai.orchestration import PipelineInput, PipelineOrchestrator
from dbt_builder.src.ai.supervision import PipelineSupervisor, SupervisorConfig

# ── Stub catalog callables ────────────────────────────────────────────────


def _list_vault_entities(catalog: str, schema: str):
    return iter([])  # empty target vault


def _describe_vault(catalog: str, schema: str, table: str):
    return iter([])


def _list_bronze_tables_factory(table_names: tuple[str, ...]):
    def _f(catalog: str, schema: str):
        return iter(table_names)

    return _f


def _describe_bronze(catalog: str, schema: str, table: str):
    # (name, dtype, nullable, comment, is_partition)
    return iter(
        [
            ("mrid", "string", False, None, False),
            ("name", "string", True, None, False),
        ]
    )


def _propose_factory(hub_names: tuple[str, ...], *, confidence=DecisionConfidence.HIGH):
    def _f(payload: DiscoveryPayload) -> ModelingPlan:
        return ModelingPlan(
            system_id=payload.system.system_id,
            hubs=tuple(
                HubDecision(
                    name=f"hub_{n}",
                    source_table=n,
                    business_keys=("mrid",),
                    hash_key=f"HK_{n.upper()}",
                    confidence=confidence,
                    rationale="stub",
                )
                for n in hub_names
            ),
        )

    return _f


def _system() -> SourceSystem:
    return SourceSystem(
        system_id="iec_cim",
        system_name="IEC CIM",
        source_type="delta",
        catalog="cat",
        schema_name="bronze",
        record_source="iec_cim",
    )


def _make_input(table_names: tuple[str, ...] = ("terminals",)) -> PipelineInput:
    return PipelineInput(
        catalog="cat",
        bronze_schema="bronze",
        vault_schema="raw_vault",
        system=_system(),
        list_vault_entities=_list_vault_entities,
        describe_vault=_describe_vault,
        list_bronze_tables=_list_bronze_tables_factory(table_names),
        describe_bronze=_describe_bronze,
    )


def _make_orch(
    *,
    hub_names: tuple[str, ...] = ("terminals",),
    supervisor: PipelineSupervisor | None = None,
    confidence=DecisionConfidence.HIGH,
) -> PipelineOrchestrator:
    return PipelineOrchestrator(
        schema_analyzer=SchemaAnalyzer(
            propose_fn=_propose_factory(hub_names, confidence=confidence)
        ),
        bv_architect=BvArchitect(),
        yaml_generator=YamlGenerator(),
        supervisor=supervisor,
    )


# ── Happy-path ─────────────────────────────────────────────────────────────


def test_full_run_reaches_done_with_all_steps() -> None:
    orch = _make_orch()
    run = orch.run(_make_input())
    assert run.status is PipelineRunStatus.DONE
    step_names = tuple(s.step for s in run.steps)
    assert step_names == (
        PipelineStepName.SNAPSHOT,
        PipelineStepName.ANALYZE,
        PipelineStepName.ARCHITECT_BV,
        PipelineStepName.GENERATE,
        PipelineStepName.VALIDATE,
    )
    assert all(s.status == "ok" for s in run.steps)
    assert run.plan is not None and run.plan.entity_count == 1
    assert run.rendered_yaml is not None and "hub_terminals" in run.rendered_yaml
    assert run.bv is not None
    assert run.validation is not None
    assert run.error_detail is None


def test_run_id_is_honoured_when_provided() -> None:
    orch = _make_orch()
    run = orch.run(_make_input(), run_id="custom-id")
    assert run.run_id == "custom-id"


def test_run_id_is_auto_generated_when_omitted() -> None:
    orch = _make_orch()
    run = orch.run(_make_input())
    assert run.run_id and len(run.run_id) > 8


# ── stop_after pause behaviour ─────────────────────────────────────────────


def test_stop_after_diff_pauses_after_snapshot() -> None:
    orch = _make_orch()
    run = orch.run(_make_input(), stop_after=StopAfter.DIFF)
    assert run.status is PipelineRunStatus.PAUSED
    assert tuple(s.step for s in run.steps) == (PipelineStepName.SNAPSHOT,)
    assert run.plan is None


def test_stop_after_plan_pauses_after_architect_bv() -> None:
    orch = _make_orch()
    run = orch.run(_make_input(), stop_after=StopAfter.PLAN)
    assert run.status is PipelineRunStatus.PAUSED
    assert PipelineStepName.ARCHITECT_BV in {s.step for s in run.steps}
    assert run.rendered_yaml is None


def test_stop_after_yaml_pauses_after_validate() -> None:
    orch = _make_orch()
    run = orch.run(_make_input(), stop_after=StopAfter.YAML)
    assert run.status is PipelineRunStatus.PAUSED
    assert PipelineStepName.VALIDATE in {s.step for s in run.steps}
    assert run.rendered_yaml is not None


# ── Failure handling ───────────────────────────────────────────────────────


def test_missing_schema_analyzer_fails_at_analyze() -> None:
    orch = PipelineOrchestrator(supervisor=None)
    run = orch.run(_make_input())
    assert run.status is PipelineRunStatus.FAILED
    last = run.steps[-1]
    assert last.step is PipelineStepName.ANALYZE
    assert last.status == "failed"
    assert "SchemaAnalyzer" in (last.error or "")


def test_snapshot_failure_short_circuits_remaining_steps() -> None:
    def boom_list(catalog: str, schema: str):
        raise RuntimeError("kaboom")

    pi = PipelineInput(
        catalog="c",
        bronze_schema="b",
        vault_schema="v",
        system=_system(),
        list_vault_entities=_list_vault_entities,
        describe_vault=_describe_vault,
        list_bronze_tables=boom_list,
        describe_bronze=_describe_bronze,
    )
    orch = _make_orch()
    run = orch.run(pi)
    assert run.status is PipelineRunStatus.FAILED
    assert len(run.steps) == 1
    assert run.steps[0].step is PipelineStepName.SNAPSHOT
    assert run.steps[0].status == "failed"
    assert "kaboom" in (run.error_detail or "")


def test_analyzer_exception_marks_run_failed() -> None:
    def boom(payload):
        raise RuntimeError("model died")

    orch = PipelineOrchestrator(
        schema_analyzer=SchemaAnalyzer(propose_fn=boom),
        supervisor=None,
    )
    run = orch.run(_make_input())
    assert run.status is PipelineRunStatus.FAILED
    assert run.steps[-1].step is PipelineStepName.ANALYZE


# ── Supervisor integration ─────────────────────────────────────────────────


def test_supervisor_pause_halts_run_when_risks_not_acknowledged() -> None:
    # Force PAUSE at SNAPSHOT by setting max_new_tables=0 so any new table
    # is HIGH severity.
    supervisor = PipelineSupervisor(config=SupervisorConfig(max_new_tables=0))
    orch = _make_orch(supervisor=supervisor)
    run = orch.run(_make_input())
    assert run.status is PipelineRunStatus.PAUSED
    assert run.risk_assessment is not None
    assert run.risk_assessment.recommendation is SupervisionRecommendation.PAUSE
    # Should not have proceeded to ANALYZE.
    assert PipelineStepName.ANALYZE not in {s.step for s in run.steps}


def test_acknowledge_risks_lets_run_continue_to_done() -> None:
    supervisor = PipelineSupervisor(config=SupervisorConfig(max_new_tables=0))
    orch = _make_orch(supervisor=supervisor)
    run = orch.run(_make_input(), acknowledge_risks=True)
    assert run.status is PipelineRunStatus.DONE
    assert run.risk_assessment is not None  # still surfaced for the UI
    assert run.rendered_yaml is not None


def test_supervisor_default_passes_when_no_risks_fire() -> None:
    # `supervisor=None` keyword falls back to the default PipelineSupervisor;
    # with a benign 1-table snapshot no risk thresholds fire and the run
    # completes.
    orch = _make_orch(supervisor=None)
    run = orch.run(_make_input())
    assert run.status is PipelineRunStatus.DONE
    # A PASS assessment may be attached from the final VALIDATE checkpoint.
    if run.risk_assessment is not None:
        assert run.risk_assessment.recommendation is SupervisionRecommendation.PASS


def test_empty_plan_pause_blocks_generate() -> None:
    # Force an empty plan and an enabled supervisor (default config pauses).
    orch = PipelineOrchestrator(
        schema_analyzer=SchemaAnalyzer(propose_fn=_propose_factory(hub_names=())),
        bv_architect=BvArchitect(),
        yaml_generator=YamlGenerator(),
    )
    # propose_factory raises in build_payload — see below.
    # Use a bronze table so build_payload succeeds, but propose returns empty.
    run = orch.run(_make_input(table_names=("terminals",)))
    # Empty plan → ARCHITECT_BV succeeds with empty bv, then supervisor PAUSE.
    assert run.status is PipelineRunStatus.PAUSED
    assert run.risk_assessment is not None


# ── Updated_at progression ─────────────────────────────────────────────────


def test_updated_at_advances_with_each_step() -> None:
    orch = _make_orch()
    run = orch.run(_make_input())
    assert run.updated_at >= run.created_at
