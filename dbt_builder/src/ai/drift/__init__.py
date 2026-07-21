"""Use Case B — schema-drift impact classification (RQ2).

The deterministic diff engine (``pipeline.diff_analyzer``) detects *what* changed;
this package classifies *what each change means* for the Data Vault — additive,
cosmetic, or breaking — via a rule-only baseline and an LLM classifier, and scores
both against expert labels (confusion matrix, per-class P/R, cost-weighted error).
"""

from __future__ import annotations

from dbt_builder.src.ai.drift.impact import (
    ChangeImpact,
    ImpactClassifier,
    ImpactVerdict,
    rule_based_impact,
)
from dbt_builder.src.ai.drift.scoring import (
    DriftImpactReport,
    impact_cost,
    score_impacts,
)

__all__ = [
    "ChangeImpact",
    "DriftImpactReport",
    "ImpactClassifier",
    "ImpactVerdict",
    "impact_cost",
    "rule_based_impact",
    "score_impacts",
]
