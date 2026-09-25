"""Scoring for schema-change impact classification (Use Case B, RQ2 / H2b).

Compares predicted impacts (rule-only or AI) against expert labels and reports:

* **accuracy** — fraction correct;
* a **confusion matrix** — expert (row) vs predicted (column);
* **per-class precision / recall** — additive / cosmetic / breaking;
* a **cost-weighted error** — because the failure modes are not equally bad:
  calling a *breaking* change non-breaking (an auto-apply that corrupts the vault)
  is far worse than a false alarm. The cost matrix makes that asymmetry explicit,
  which is the safety-relevant number for the thesis.

Pure and deterministic: plain label lists in, a report out. No I/O, no LLM.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.drift.impact import ChangeImpact

# Cost of each (expert, predicted) outcome. The dangerous error — under-calling a
# breaking change — dominates; a false alarm (over-calling breaking) is cheap;
# an additive<->cosmetic mix-up is minor. Correct predictions cost nothing.
_MISS_BREAKING_COST = 5  # expert BREAKING, predicted non-breaking (unsafe)
_FALSE_ALARM_COST = 1  # expert non-breaking, predicted BREAKING (safe but noisy)
_MINOR_CONFUSION_COST = 1  # additive <-> cosmetic


def impact_cost(expert: ChangeImpact, predicted: ChangeImpact) -> int:
    """Asymmetric cost of predicting ``predicted`` when the truth is ``expert``."""
    if expert is predicted:
        return 0
    if expert is ChangeImpact.BREAKING:
        return _MISS_BREAKING_COST  # missed a breaking change — the dangerous case
    if predicted is ChangeImpact.BREAKING:
        return _FALSE_ALARM_COST  # over-cautious — just needs a human glance
    return _MINOR_CONFUSION_COST  # additive vs cosmetic, both non-breaking


class ClassMetrics(BaseModel):
    """Precision / recall / support for one impact class."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    support: int = Field(ge=0)  # expert count of this class
    true_positive: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)

    @property
    def precision(self) -> float:
        denom = self.true_positive + self.false_positive
        return 1.0 if denom == 0 else self.true_positive / denom

    @property
    def recall(self) -> float:
        denom = self.true_positive + self.false_negative
        return 1.0 if denom == 0 else self.true_positive / denom


class DriftImpactReport(BaseModel):
    """Result of scoring predicted impacts against expert labels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    n: int = Field(ge=0)
    correct: int = Field(ge=0)
    total_cost: int = Field(ge=0)
    confusion: dict[str, dict[str, int]]  # expert -> predicted -> count
    per_class: dict[str, ClassMetrics]

    @property
    def accuracy(self) -> float:
        return 1.0 if self.n == 0 else self.correct / self.n

    @property
    def breaking_recall(self) -> float:
        """Recall on the breaking class — the safety-critical number."""
        return self.per_class[ChangeImpact.BREAKING.value].recall


def score_impacts(
    predicted: Sequence[ChangeImpact], expert: Sequence[ChangeImpact]
) -> DriftImpactReport:
    """Score ``predicted`` against ``expert`` labels (same order, same length)."""
    if len(predicted) != len(expert):
        raise ValueError(
            f"predicted ({len(predicted)}) and expert ({len(expert)}) lengths differ"
        )
    classes = [c.value for c in ChangeImpact]
    confusion = {e: {p: 0 for p in classes} for e in classes}
    correct = 0
    total_cost = 0
    for pred, exp in zip(predicted, expert, strict=True):
        confusion[exp.value][pred.value] += 1
        if pred is exp:
            correct += 1
        total_cost += impact_cost(exp, pred)

    per_class: dict[str, ClassMetrics] = {}
    for c in classes:
        tp = confusion[c][c]
        fp = sum(confusion[e][c] for e in classes if e != c)  # predicted c, expert not c
        fn = sum(confusion[c][p] for p in classes if p != c)  # expert c, predicted not c
        per_class[c] = ClassMetrics(
            support=sum(confusion[c].values()), true_positive=tp,
            false_positive=fp, false_negative=fn,
        )

    return DriftImpactReport(
        n=len(predicted), correct=correct, total_cost=total_cost,
        confusion=confusion, per_class=per_class,
    )


__all__ = ["ClassMetrics", "DriftImpactReport", "impact_cost", "score_impacts"]
