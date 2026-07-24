"""Experiment 7 — governance safety floor (H3a). Deterministic, no network.

Experiment 7 measured a 62% block rate: the diff engine computed per-change risk,
but nothing consulted it, so breaking schema changes (business-key retype, dropped
column, vanished source) flowed straight through the gate. These tests lock in the
fix — the supervisor now escalates any change the deterministic impact rule calls
BREAKING to a HIGH signal — and guard against over-blocking benign drift.
"""

from __future__ import annotations

from datetime import datetime, timezone

from dbt_builder.src.ai.contracts.catalog import (
    ChangeCategory,
    ChangeRisk,
    ChangeSet,
    ColumnDiff,
    TableChange,
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
from dbt_builder.src.ai.supervision import PipelineSupervisor
from dbt_builder.src.ai.supervision.supervisor import SupervisorConfig

NOW = datetime.now(timezone.utc)


def _run(*changes: TableChange) -> PipelineRun:
    cs = ChangeSet(catalog="c", schema_name="s", computed_at=NOW, changes=changes)
    base = PipelineRun(run_id="r", status=PipelineRunStatus.RUNNING, created_at=NOW, updated_at=NOW)
    return base.model_copy(update={"change_set": cs})


def _assess(run: PipelineRun, cfg: SupervisorConfig | None = None):
    return PipelineSupervisor(config=cfg).evaluate(run, after_step=PipelineStepName.SNAPSHOT)


def _diff(name: str, verb: str, old: str | None = None, new: str | None = None) -> ColumnDiff:
    return ColumnDiff(name=name, change=verb, old_dtype=old, new_dtype=new)


def _unchanged(name: str) -> TableChange:
    return TableChange(table_name=name, category=ChangeCategory.UNCHANGED)


# ── the three gaps Experiment 7 found (now blocked) ──────────────────────────


def test_business_key_retype_pauses_the_run():
    run = _run(
        TableChange(
            table_name="conducting_equipment", category=ChangeCategory.DRIFT,
            risk=ChangeRisk.HIGH,
            column_diffs=(_diff("mrid", "type_changed", "string", "bigint"),),
        ),
        _unchanged("other"),
    )
    a = _assess(run)
    assert a.recommendation is SupervisionRecommendation.PAUSE
    assert a.max_severity is RiskSeverity.HIGH
    assert any(s.kind is RiskKind.BREAKING_SCHEMA_CHANGE for s in a.signals)


def test_orphaned_table_pauses_the_run():
    run = _run(
        TableChange(table_name="connectivity_nodes", category=ChangeCategory.ORPHANED),
        _unchanged("other"),
    )
    a = _assess(run)
    assert a.recommendation is SupervisionRecommendation.PAUSE
    assert any(s.kind is RiskKind.BREAKING_SCHEMA_CHANGE for s in a.signals)


def test_removed_column_pauses_the_run():
    run = _run(
        TableChange(
            table_name="t", category=ChangeCategory.DRIFT, risk=ChangeRisk.MEDIUM,
            column_diffs=(_diff("serial_number", "removed", old="string"),),
        ),
        _unchanged("u"),
        _unchanged("v"),
    )
    a = _assess(run)
    assert a.recommendation is SupervisionRecommendation.PAUSE
    assert any(s.kind is RiskKind.BREAKING_SCHEMA_CHANGE for s in a.signals)


# ── guard against over-blocking (benign drift must still pass) ───────────────


def test_additive_only_drift_does_not_pause():
    # A new nullable column is forward-compatible — the gate must not cry wolf.
    run = _run(
        TableChange(
            table_name="t", category=ChangeCategory.DRIFT, risk=ChangeRisk.MEDIUM,
            column_diffs=(_diff("owner", "added", new="string"),),
        ),
        _unchanged("u"),
        _unchanged("v"),
    )
    a = _assess(run)
    assert not any(s.kind is RiskKind.BREAKING_SCHEMA_CHANGE for s in a.signals)
    assert a.recommendation is SupervisionRecommendation.PASS


def test_new_table_alone_does_not_pause():
    run = _run(
        TableChange(table_name="cim_measurements", category=ChangeCategory.NEW),
        _unchanged("u"),
        _unchanged("v"),
    )
    a = _assess(run)
    assert a.recommendation is SupervisionRecommendation.PASS


def test_unchanged_snapshot_raises_no_signals():
    a = _assess(_run(_unchanged("a"), _unchanged("b")))
    assert a.signals == ()
    assert a.recommendation is SupervisionRecommendation.PASS


# ── the floor is configurable (deployments may opt out explicitly) ───────────


def test_safety_floor_can_be_disabled():
    run = _run(
        TableChange(table_name="x", category=ChangeCategory.ORPHANED),
        _unchanged("other"),
    )
    a = _assess(run, SupervisorConfig(pause_on_breaking_change=False))
    assert not any(s.kind is RiskKind.BREAKING_SCHEMA_CHANGE for s in a.signals)
