"""Experiment harness: bundle every metric per plan and run the ablation study.

This is the top of the evaluation stack. :func:`evaluate_plan` collapses a
:class:`ModelingPlan` into a flat :class:`PlanMetrics` bundle (conformance +
coverage + blast-radius + optional gold P/R/F1) suitable for logging to a table
or CSV. :func:`run_ablation` runs a set of *arms* (e.g. learning OFF vs ON, or
increasing corpus sizes for the learning curve) over a set of cases and returns
the per-arm mean metrics — the numbers that go in the dissertation.

The modelling call is injected as ``propose(arm, case) -> ModelingPlan`` so the
harness is pure and unit-testable; production wires it to
``get_modelling_agent(...).propose(case.payload)`` with ``learning_examples_*``
settings varied per arm.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from statistics import fmean
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.evaluation.blast_radius import (
    plan_blast_radius,
    weighted_error_impact,
)
from dbt_builder.src.ai.evaluation.conformance import score_plan
from dbt_builder.src.ai.evaluation.coverage import coverage
from dbt_builder.src.ai.evaluation.gold import GoldModel, grade_against_gold

# Scalar PlanMetrics fields averaged by :func:`aggregate`. Gold_* are optional
# and averaged only over the cases that actually have a gold model.
_SCALAR_FIELDS = (
    "n_hubs",
    "n_links",
    "n_satellites",
    "conformance_score",
    "issue_count",
    "weighted_error_impact",
    "max_blast_radius",
    "coverage_ratio",
    "uncovered_count",
)
_GOLD_FIELDS = ("gold_hub_f1", "gold_link_f1", "gold_sat_f1", "gold_macro_f1", "gold_bk_accuracy")


class PlanMetrics(BaseModel):
    """Every quality metric for one plan, flattened for logging / aggregation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_id: str
    n_hubs: int = Field(ge=0)
    n_links: int = Field(ge=0)
    n_satellites: int = Field(ge=0)
    conformance_score: float
    issue_count: int = Field(ge=0)
    weighted_error_impact: int = Field(ge=0)
    max_blast_radius: int = Field(ge=0)
    coverage_ratio: float
    uncovered_count: int = Field(ge=0)
    issues_by_type: dict[str, int] = Field(default_factory=dict)
    # Present only when a gold model was supplied.
    gold_hub_f1: float | None = None
    gold_link_f1: float | None = None
    gold_sat_f1: float | None = None
    gold_macro_f1: float | None = None
    gold_bk_accuracy: float | None = None


def evaluate_plan(
    plan: ModelingPlan,
    *,
    source_tables: Sequence[str] = (),
    gold: GoldModel | None = None,
    technical_columns: frozenset[str] = frozenset(),
) -> PlanMetrics:
    """Score ``plan`` across every dimension into one :class:`PlanMetrics`."""
    conf = score_plan(plan, technical_columns=technical_columns)
    cov = coverage(plan, source_tables)
    blast = plan_blast_radius(plan)

    gold_fields: dict[str, float] = {}
    if gold is not None:
        g = grade_against_gold(plan, gold)
        gold_fields = {
            "gold_hub_f1": g.hubs.f1,
            "gold_link_f1": g.links.f1,
            "gold_sat_f1": g.satellites.f1,
            "gold_macro_f1": g.macro_f1,
            "gold_bk_accuracy": g.business_key_accuracy,
        }

    return PlanMetrics(
        system_id=plan.system_id,
        n_hubs=len(plan.hubs),
        n_links=len(plan.links),
        n_satellites=len(plan.satellites),
        conformance_score=conf.score,
        issue_count=len(conf.issues),
        weighted_error_impact=weighted_error_impact(plan, conf),
        max_blast_radius=blast.max_radius,
        coverage_ratio=cov.coverage_ratio,
        uncovered_count=len(cov.uncovered),
        issues_by_type=conf.issues_by_type,
        **gold_fields,
    )


def aggregate(metrics: Sequence[PlanMetrics]) -> dict[str, float]:
    """Mean of every scalar metric across ``metrics`` (empty -> empty dict).

    Gold_* fields are averaged only over the plans that carry them, so a mixed
    batch (some cases have a gold model, some don't) reports honest gold means.
    """
    if not metrics:
        return {}
    out: dict[str, float] = {"n_cases": float(len(metrics))}
    for f in _SCALAR_FIELDS:
        out[f] = fmean(getattr(m, f) for m in metrics)
    for f in _GOLD_FIELDS:
        vals = [getattr(m, f) for m in metrics if getattr(m, f) is not None]
        if vals:
            out[f] = fmean(vals)
    return out


@dataclass(frozen=True)
class ExperimentCase:
    """One source system to model + how to score it."""

    system_id: str
    source_tables: tuple[str, ...] = ()
    gold: GoldModel | None = None
    payload: Any = None  # opaque; forwarded to the propose callable


@dataclass(frozen=True)
class AblationArm:
    """One experimental condition (e.g. learning OFF vs ON, or corpus size N)."""

    label: str
    config: dict[str, Any] = field(default_factory=dict)


def run_ablation(
    cases: Sequence[ExperimentCase],
    *,
    propose: Callable[[AblationArm, ExperimentCase], ModelingPlan],
    arms: Sequence[AblationArm],
    technical_columns: frozenset[str] = frozenset(),
) -> dict[str, dict[str, float]]:
    """Run every ``arm`` over every case; return per-arm mean metrics.

    ``propose(arm, case)`` produces the plan for that condition — in production
    it builds a modelling agent with the arm's ``config`` (e.g.
    ``learning_examples_enabled`` / ``learning_examples_k``) and calls
    ``propose(case.payload)``. A learning curve is just a series of arms whose
    config seeds an increasing corpus size.
    """
    results: dict[str, dict[str, float]] = {}
    for arm in arms:
        per_case: list[PlanMetrics] = []
        for case in cases:
            plan = propose(arm, case)
            per_case.append(
                evaluate_plan(
                    plan,
                    source_tables=case.source_tables,
                    gold=case.gold,
                    technical_columns=technical_columns,
                )
            )
        results[arm.label] = aggregate(per_case)
    return results


__all__ = [
    "AblationArm",
    "ExperimentCase",
    "PlanMetrics",
    "aggregate",
    "evaluate_plan",
    "run_ablation",
]
