"""Tests for :class:`PipelineSupervisor` — deterministic risk assessment."""

from __future__ import annotations

from datetime import datetime, timezone

from dbt_builder.src.ai.contracts.catalog import (
    ChangeCategory,
    ChangeSet,
    TableChange,
)
from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    HubDecision,
    ModelingPlan,
)
from dbt_builder.src.ai.contracts.pipeline_run import (
    PipelineRun,
    PipelineRunStatus,
    PipelineStepName,
)
from dbt_builder.src.ai.contracts.supervision import (
    RiskKind,
    RiskSeverity,
    SupervisionRecommendation,
)
from dbt_builder.src.ai.contracts.validation import (
    CheckSummary,
    ValidationReport,
)
from dbt_builder.src.ai.supervision import PipelineSupervisor, SupervisorConfig

# ── Helpers ────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime(2026, 5, 23, tzinfo=timezone.utc)


def _run(**overrides) -> PipelineRun:
    base = {
        "run_id": "r1",
        "status": PipelineRunStatus.RUNNING,
        "created_at": _now(),
        "updated_at": _now(),
    }
    base.update(overrides)
    return PipelineRun(**base)


def _change_set(*, new: int = 0, drift: int = 0, orphan: int = 0, unchanged: int = 0) -> ChangeSet:
    changes = []
    for i in range(new):
        changes.append(TableChange(table_name=f"new_{i}", category=ChangeCategory.NEW))
    for i in range(drift):
        changes.append(TableChange(table_name=f"drift_{i}", category=ChangeCategory.DRIFT))
    for i in range(orphan):
        changes.append(TableChange(table_name=f"orph_{i}", category=ChangeCategory.ORPHANED))
    for i in range(unchanged):
        changes.append(TableChange(table_name=f"keep_{i}", category=ChangeCategory.UNCHANGED))
    return ChangeSet(catalog="c", schema_name="s", computed_at=_now(), changes=tuple(changes))


def _plan(*, hub_confidences: tuple[DecisionConfidence, ...] = ()) -> ModelingPlan:
    hubs = tuple(
        HubDecision(
            name=f"hub_t{i}",
            source_table=f"t{i}",
            business_keys=("mrid",),
            hash_key=f"HK_T{i}",
            confidence=c,
            rationale="x",
        )
        for i, c in enumerate(hub_confidences)
    )
    return ModelingPlan(system_id="sys", hubs=hubs)


def _validation(*, errors: int = 0, warnings: int = 0) -> ValidationReport:
    return ValidationReport(
        plan_id="sys",
        computed_at=_now(),
        summary=CheckSummary(errors=errors, warnings=warnings),
    )


# ── SNAPSHOT assessments ───────────────────────────────────────────────────


def test_snapshot_no_change_set_returns_empty_assessment() -> None:
    sup = PipelineSupervisor()
    a = sup.evaluate(_run(), after_step=PipelineStepName.SNAPSHOT)
    assert a is not None
    assert a.signals == ()
    assert a.recommendation is SupervisionRecommendation.PASS


def test_snapshot_high_new_tables_triggers_high_severity_pause() -> None:
    sup = PipelineSupervisor(config=SupervisorConfig(max_new_tables=3))
    a = sup.evaluate(_run(change_set=_change_set(new=10)), after_step=PipelineStepName.SNAPSHOT)
    assert a is not None
    kinds = {s.kind for s in a.signals}
    assert RiskKind.HIGH_NEW_TABLE_VOLUME in kinds
    assert a.max_severity is RiskSeverity.HIGH
    assert a.recommendation is SupervisionRecommendation.PAUSE


def test_snapshot_below_new_table_threshold_passes() -> None:
    sup = PipelineSupervisor(config=SupervisorConfig(max_new_tables=15))
    a = sup.evaluate(_run(change_set=_change_set(new=5)), after_step=PipelineStepName.SNAPSHOT)
    assert a is not None
    assert a.recommendation is SupervisionRecommendation.PASS


def test_snapshot_high_drift_fraction_is_medium() -> None:
    sup = PipelineSupervisor(config=SupervisorConfig(drift_fraction_threshold=0.30))
    # 6 drift / 10 total = 60% > 30%
    a = sup.evaluate(
        _run(change_set=_change_set(drift=6, unchanged=4)),
        after_step=PipelineStepName.SNAPSHOT,
    )
    assert a is not None
    kinds = {s.kind for s in a.signals}
    assert RiskKind.HIGH_DRIFT_FRACTION in kinds
    # One medium signal alone → still PASS
    assert a.recommendation is SupervisionRecommendation.PASS


def test_snapshot_orphans_flagged_only_when_configured() -> None:
    cs = _change_set(orphan=2, unchanged=3)
    off = PipelineSupervisor(config=SupervisorConfig(pause_on_any_orphan=False))
    on = PipelineSupervisor(config=SupervisorConfig(pause_on_any_orphan=True))
    a_off = off.evaluate(_run(change_set=cs), after_step=PipelineStepName.SNAPSHOT)
    a_on = on.evaluate(_run(change_set=cs), after_step=PipelineStepName.SNAPSHOT)
    assert a_off is not None and a_on is not None
    assert all(s.kind is not RiskKind.ORPHANED_ENTITIES_PRESENT for s in a_off.signals)
    assert any(s.kind is RiskKind.ORPHANED_ENTITIES_PRESENT for s in a_on.signals)


# ── PLAN assessments ───────────────────────────────────────────────────────


def test_plan_empty_triggers_pause_when_configured() -> None:
    sup = PipelineSupervisor()
    a = sup.evaluate(_run(plan=_plan()), after_step=PipelineStepName.ARCHITECT_BV)
    assert a is not None
    assert {s.kind for s in a.signals} == {RiskKind.EMPTY_PLAN}
    assert a.recommendation is SupervisionRecommendation.PAUSE


def test_plan_empty_ignored_when_disabled() -> None:
    sup = PipelineSupervisor(config=SupervisorConfig(pause_on_empty_plan=False))
    a = sup.evaluate(_run(plan=_plan()), after_step=PipelineStepName.ARCHITECT_BV)
    assert a is not None
    assert a.signals == ()


def test_plan_low_confidence_fraction_flags_medium() -> None:
    sup = PipelineSupervisor(config=SupervisorConfig(low_confidence_fraction_threshold=0.30))
    plan = _plan(
        hub_confidences=(
            DecisionConfidence.LOW,
            DecisionConfidence.LOW,
            DecisionConfidence.HIGH,
            DecisionConfidence.HIGH,
        )
    )
    a = sup.evaluate(_run(plan=plan), after_step=PipelineStepName.ARCHITECT_BV)
    assert a is not None
    assert any(s.kind is RiskKind.LOW_CONFIDENCE_DECISIONS for s in a.signals)


# ── VALIDATION assessments ─────────────────────────────────────────────────


def test_validation_failure_triggers_high_pause() -> None:
    sup = PipelineSupervisor()
    a = sup.evaluate(
        _run(validation=_validation(errors=2)),
        after_step=PipelineStepName.VALIDATE,
    )
    assert a is not None
    assert {s.kind for s in a.signals} == {RiskKind.VALIDATION_ERRORS}
    assert a.recommendation is SupervisionRecommendation.PAUSE


def test_validation_many_warnings_flags_medium() -> None:
    sup = PipelineSupervisor(config=SupervisorConfig(max_validation_warnings=5))
    a = sup.evaluate(
        _run(validation=_validation(warnings=20)),
        after_step=PipelineStepName.VALIDATE,
    )
    assert a is not None
    assert any(s.kind is RiskKind.VALIDATION_WARNINGS for s in a.signals)


def test_validation_clean_passes() -> None:
    sup = PipelineSupervisor()
    a = sup.evaluate(
        _run(validation=_validation()),
        after_step=PipelineStepName.VALIDATE,
    )
    assert a is not None
    assert a.signals == ()
    assert a.recommendation is SupervisionRecommendation.PASS


# ── Recommendation derivation ──────────────────────────────────────────────


def test_two_medium_signals_combine_to_pause() -> None:
    sup = PipelineSupervisor(
        config=SupervisorConfig(
            drift_fraction_threshold=0.10,
            pause_on_any_orphan=True,
        )
    )
    cs = _change_set(drift=5, orphan=3, unchanged=2)  # both medium kinds fire
    a = sup.evaluate(_run(change_set=cs), after_step=PipelineStepName.SNAPSHOT)
    assert a is not None
    assert len(a.signals) >= 2
    assert a.recommendation is SupervisionRecommendation.PAUSE


# ── Step dispatch ──────────────────────────────────────────────────────────


def test_unsupervised_step_returns_none() -> None:
    sup = PipelineSupervisor()
    assert sup.evaluate(_run(), after_step=PipelineStepName.ANALYZE) is None
    assert sup.evaluate(_run(), after_step=PipelineStepName.GENERATE) is None
