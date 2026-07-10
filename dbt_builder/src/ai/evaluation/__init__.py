"""Model-quality evaluation for the feedback-learning study.

Ground-truth-free metrics over a :class:`ModelingPlan`:

* :func:`score_plan` — DV2 convention conformance + typed error taxonomy.
* :func:`coverage` — input (source tables) -> output (objects) completeness.
* :func:`plan_blast_radius` / :func:`weighted_error_impact` — how far errors
  propagate, so severity can be weighted by dependency fan-out.

All pure and deterministic. Gold-set precision/recall (Phase 5) and the
experiment runner (Phase 6) build on these.
"""

from __future__ import annotations

from dbt_builder.src.ai.evaluation.blast_radius import (
    BlastRadiusReport,
    plan_blast_radius,
    weighted_error_impact,
)
from dbt_builder.src.ai.evaluation.conformance import (
    ConformanceIssue,
    ConformanceReport,
    IssueType,
    score_plan,
)
from dbt_builder.src.ai.evaluation.coverage import CoverageReport, coverage
from dbt_builder.src.ai.evaluation.gold import (
    GoldModel,
    GoldScore,
    PrecisionRecall,
    grade_against_gold,
    load_gold_models,
)

__all__ = [
    "BlastRadiusReport",
    "ConformanceIssue",
    "ConformanceReport",
    "CoverageReport",
    "GoldModel",
    "GoldScore",
    "IssueType",
    "PrecisionRecall",
    "coverage",
    "grade_against_gold",
    "load_gold_models",
    "plan_blast_radius",
    "score_plan",
    "weighted_error_impact",
]
