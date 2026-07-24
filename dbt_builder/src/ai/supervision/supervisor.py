"""Risk-based pipeline supervisor.

All assessments are purely deterministic — no LLM calls.  Thresholds are
collected in :class:`SupervisorConfig` (single source of truth; no magic
numbers scattered across the codebase).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dbt_builder.src.ai.contracts.supervision import (
    RiskAssessment,
    RiskKind,
    RiskSeverity,
    RiskSignal,
    SupervisionRecommendation,
)

if TYPE_CHECKING:
    from dbt_builder.src.ai.contracts.pipeline_run import PipelineRun, PipelineStepName

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class SupervisorConfig:
    """All supervisor thresholds in one immutable place.

    Defaults reflect practical experience with medium-sized source systems
    (~30–50 tables).  Override per deployment by injecting a custom instance.
    """

    # ── SNAPSHOT thresholds ───────────────────────────────────────────────
    max_new_tables: int = 15
    drift_fraction_threshold: float = 0.40
    pause_on_any_orphan: bool = False
    # Safety floor: halt when the deterministic impact rule calls any detected
    # change BREAKING (business-key retype, dropped column, vanished source).
    # Added after Experiment 7 measured a 62% block rate: the diff engine already
    # computed per-change risk, but nothing consulted it, so breaking schema
    # changes flowed straight through the gate.
    pause_on_breaking_change: bool = True

    # ── PLAN thresholds ───────────────────────────────────────────────────
    low_confidence_fraction_threshold: float = 0.40
    pause_on_empty_plan: bool = True

    # ── VALIDATION thresholds ─────────────────────────────────────────────
    pause_on_validation_errors: bool = True
    max_validation_warnings: int = 10


# ── Internal helpers ─────────────────────────────────────────────────────────


_SEVERITY_RANK: dict[RiskSeverity, int] = {
    RiskSeverity.LOW: 0,
    RiskSeverity.MEDIUM: 1,
    RiskSeverity.HIGH: 2,
}


def _derive_recommendation(signals: tuple[RiskSignal, ...]) -> SupervisionRecommendation:
    """Derive the top-level recommendation from the signal set."""
    high_count = sum(1 for s in signals if s.severity is RiskSeverity.HIGH)
    medium_count = sum(1 for s in signals if s.severity is RiskSeverity.MEDIUM)
    if high_count > 0 or medium_count >= 2:
        return SupervisionRecommendation.PAUSE
    return SupervisionRecommendation.PASS


def _max_severity(signals: tuple[RiskSignal, ...]) -> RiskSeverity:
    if not signals:
        return RiskSeverity.LOW
    return max(signals, key=lambda s: _SEVERITY_RANK[s.severity]).severity


# ── Supervisor ────────────────────────────────────────────────────────────────


class PipelineSupervisor:
    """Deterministic risk assessor called by the orchestrator after each step.

    Stateless: all context is passed per-call via the ``run`` artifact and the
    ``after_step`` name.
    """

    def __init__(self, *, config: SupervisorConfig | None = None) -> None:
        self._cfg = config or SupervisorConfig()

    def evaluate(
        self,
        run: PipelineRun,
        *,
        after_step: PipelineStepName,
    ) -> RiskAssessment | None:
        """Assess risk after ``after_step`` and return a :class:`RiskAssessment`.

        Returns ``None`` when no assessment is registered for the given step.
        """
        from dbt_builder.src.ai.contracts.pipeline_run import PipelineStepName as _Step

        dispatch = {
            _Step.SNAPSHOT: self._assess_after_snapshot,
            _Step.ARCHITECT_BV: self._assess_after_plan,
            _Step.VALIDATE: self._assess_after_validation,
        }
        handler = dispatch.get(after_step)
        if handler is None:
            return None

        signals = tuple(handler(run))
        return RiskAssessment(
            assessed_after_step=after_step.value,
            signals=signals,
            max_severity=_max_severity(signals),
            recommendation=_derive_recommendation(signals),
        )

    # ── per-step assessors ───────────────────────────────────────────────────

    def _assess_after_snapshot(self, run: PipelineRun) -> list[RiskSignal]:
        signals: list[RiskSignal] = []
        change_set = run.change_set
        if change_set is None:
            return signals

        from dbt_builder.src.ai.contracts.catalog import ChangeCategory

        total = len(change_set.changes)
        new_count = sum(1 for c in change_set.changes if c.category is ChangeCategory.NEW)
        drift_count = sum(1 for c in change_set.changes if c.category is ChangeCategory.DRIFT)

        if new_count > self._cfg.max_new_tables:
            signals.append(
                RiskSignal(
                    kind=RiskKind.HIGH_NEW_TABLE_VOLUME,
                    severity=RiskSeverity.HIGH,
                    detail=(
                        f"{new_count} new tables discovered — exceeds threshold of "
                        f"{self._cfg.max_new_tables}."
                    ),
                )
            )

        drift_fraction = drift_count / total if total else 0.0
        if drift_fraction > self._cfg.drift_fraction_threshold:
            signals.append(
                RiskSignal(
                    kind=RiskKind.HIGH_DRIFT_FRACTION,
                    severity=RiskSeverity.MEDIUM,
                    detail=(
                        f"{drift_count}/{total} tables ({drift_fraction:.0%}) drifted — "
                        f"exceeds threshold of {self._cfg.drift_fraction_threshold:.0%}."
                    ),
                )
            )

        # Safety floor (H3a): escalate any change the deterministic impact rule
        # classifies BREAKING. Reuses the Use-Case-B rule (no LLM, conservative)
        # rather than duplicating the logic, so the gate acts on the risk the diff
        # engine already computed. A pause — the operator can still acknowledge.
        if self._cfg.pause_on_breaking_change:
            from dbt_builder.src.ai.drift.impact import ChangeImpact, rule_based_impact

            breaking = [
                c for c in change_set.changes if rule_based_impact(c) is ChangeImpact.BREAKING
            ]
            if breaking:
                names = ", ".join(sorted(c.table_name for c in breaking)[:5])
                signals.append(
                    RiskSignal(
                        kind=RiskKind.BREAKING_SCHEMA_CHANGE,
                        severity=RiskSeverity.HIGH,
                        detail=(
                            f"{len(breaking)} breaking schema change(s) detected "
                            f"({names}) — review before applying."
                        ),
                    )
                )

        if self._cfg.pause_on_any_orphan:
            orphan_count = sum(
                1 for c in change_set.changes if c.category is ChangeCategory.ORPHANED
            )
            if orphan_count > 0:
                signals.append(
                    RiskSignal(
                        kind=RiskKind.ORPHANED_ENTITIES_PRESENT,
                        severity=RiskSeverity.MEDIUM,
                        detail=(f"{orphan_count} vault entities have no matching bronze table."),
                    )
                )

        return signals

    def _assess_after_plan(self, run: PipelineRun) -> list[RiskSignal]:
        signals: list[RiskSignal] = []
        plan = run.plan
        if plan is None:
            return signals

        from dbt_builder.src.ai.contracts.decisions import DecisionConfidence

        if self._cfg.pause_on_empty_plan and plan.entity_count == 0:
            signals.append(
                RiskSignal(
                    kind=RiskKind.EMPTY_PLAN,
                    severity=RiskSeverity.HIGH,
                    detail=(
                        "The modelling agent produced a plan with zero entities. "
                        "Inspect the prompt and payload before retrying."
                    ),
                )
            )
            return signals

        hub_count = len(plan.hubs)
        if hub_count > 0:
            low_count = sum(1 for h in plan.hubs if h.confidence is DecisionConfidence.LOW)
            low_fraction = low_count / hub_count
            if low_fraction > self._cfg.low_confidence_fraction_threshold:
                signals.append(
                    RiskSignal(
                        kind=RiskKind.LOW_CONFIDENCE_DECISIONS,
                        severity=RiskSeverity.MEDIUM,
                        detail=(
                            f"{low_count}/{hub_count} hub decisions are LOW confidence "
                            f"({low_fraction:.0%}) — exceeds threshold of "
                            f"{self._cfg.low_confidence_fraction_threshold:.0%}."
                        ),
                    )
                )

        return signals

    def _assess_after_validation(self, run: PipelineRun) -> list[RiskSignal]:
        signals: list[RiskSignal] = []
        validation = run.validation
        if validation is None:
            return signals

        if self._cfg.pause_on_validation_errors and not validation.passed:
            signals.append(
                RiskSignal(
                    kind=RiskKind.VALIDATION_ERRORS,
                    severity=RiskSeverity.HIGH,
                    detail=(
                        f"Validation failed with {validation.summary.errors} error(s). "
                        "Fix the issues before approval."
                    ),
                )
            )
        elif validation.summary.warnings > self._cfg.max_validation_warnings:
            signals.append(
                RiskSignal(
                    kind=RiskKind.VALIDATION_WARNINGS,
                    severity=RiskSeverity.MEDIUM,
                    detail=(
                        f"{validation.summary.warnings} validation warnings — "
                        f"exceeds threshold of {self._cfg.max_validation_warnings}."
                    ),
                )
            )

        return signals
