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

from dbt_builder.src.ai.evaluation.baselines import HeuristicClassifier
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
from dbt_builder.src.ai.evaluation.experiment import (
    AblationArm,
    ExperimentCase,
    PlanMetrics,
    aggregate,
    evaluate_plan,
    run_ablation,
)
from dbt_builder.src.ai.evaluation.gold import (
    CorrectionReport,
    GoldHub,
    GoldModel,
    GoldScore,
    PrecisionRecall,
    build_from_scratch_steps,
    correction_steps,
    grade_against_gold,
    load_gold_models,
)
from dbt_builder.src.ai.evaluation.study import (
    Condition,
    StageRecord,
    StageSummary,
    TaxonomyShift,
    Wiring,
    build_modeller,
    parse_condition,
    resolve_payload_path,
    run_condition,
    run_study,
    summarise,
    taxonomy_shift,
)

__all__ = [
    "AblationArm",
    "BlastRadiusReport",
    "Condition",
    "CorrectionReport",
    "ConformanceIssue",
    "ConformanceReport",
    "CoverageReport",
    "ExperimentCase",
    "HeuristicClassifier",
    "GoldHub",
    "GoldModel",
    "GoldScore",
    "IssueType",
    "PlanMetrics",
    "PrecisionRecall",
    "StageRecord",
    "StageSummary",
    "TaxonomyShift",
    "Wiring",
    "aggregate",
    "build_from_scratch_steps",
    "build_modeller",
    "correction_steps",
    "coverage",
    "evaluate_plan",
    "grade_against_gold",
    "load_gold_models",
    "parse_condition",
    "plan_blast_radius",
    "resolve_payload_path",
    "run_ablation",
    "run_condition",
    "run_study",
    "score_plan",
    "summarise",
    "taxonomy_shift",
    "weighted_error_impact",
]
