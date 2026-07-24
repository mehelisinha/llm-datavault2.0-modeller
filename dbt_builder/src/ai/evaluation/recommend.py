"""Approval recommendation — turn the metric scorecard into a plain-language verdict.

A reviewer who is not a Data-Vault expert cannot judge a generated plan by reading
its YAML. This module distils the objective checks already computed elsewhere
(source grounding, DV2 conformance, and — when a reference model exists — gold
grading) into one of three verdicts with human-readable reasons:

* **REJECT** — an *objective* defect: the plan references source structure that does
  not exist (a hallucination), or it is empty. These are unambiguously wrong and
  should never enter the learning corpus.
* **REVIEW** — something imperfect that needs a human eye: a convention issue,
  over-linking, an unfollowed naming convention, or the absence of any reference
  model to check correctness against.
* **APPROVE** — nothing was flagged: grounded, conformant, and (where a reference
  exists) a perfect entity match with the shop naming convention.

The verdict leans on **objective binary signals** rather than tuned thresholds, so
it is defensible without magic numbers: REJECT is driven by fabricated references
and empty plans; APPROVE requires *nothing* to be flagged; everything in between is
REVIEW with the specifics listed. The reasons double as an auto-generated,
meaningful rejection message — so a non-expert can reject informatively.

Pure and deterministic: reports in, a recommendation out. No I/O, no LLM.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from dbt_builder.src.ai.evaluation.conformance import ConformanceReport
from dbt_builder.src.ai.evaluation.gold import GoldScore
from dbt_builder.src.ai.evaluation.grounding import GroundingReport


class ApprovalVerdict(str, Enum):
    """The recommendation shown to a human reviewer."""

    APPROVE = "approve"  # nothing flagged
    REVIEW = "review"  # imperfect — a human should look
    REJECT = "reject"  # an objective defect — do not store


class ApprovalRecommendation(BaseModel):
    """A verdict plus the concrete reasons behind it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: ApprovalVerdict
    blocking_reasons: tuple[str, ...] = ()  # drive a REJECT
    review_reasons: tuple[str, ...] = ()  # drive a REVIEW

    @property
    def rejection_message(self) -> str:
        """A meaningful, auto-generated comment for a REJECT (or REVIEW) decision."""
        reasons = self.blocking_reasons or self.review_reasons
        return "; ".join(reasons) if reasons else "no issues detected"


def recommend_approval(
    *,
    conformance: ConformanceReport,
    grounding: GroundingReport | None = None,
    gold: GoldScore | None = None,
) -> ApprovalRecommendation:
    """Recommend APPROVE / REVIEW / REJECT from the objective checks.

    ``grounding`` and ``gold`` are optional: grounding needs the source payload, and
    a gold score exists only for systems with a hand-authored reference. When either
    is absent the recommendation degrades gracefully — with no reference model it can
    never rise above REVIEW, because correctness cannot be verified.
    """
    blocking: list[str] = []
    review: list[str] = []

    # ── objective defects → REJECT ────────────────────────────────────────────
    if grounding is not None and grounding.fabricated_references > 0:
        for ref in (*grounding.fabricated_tables, *grounding.fabricated_columns):
            blocking.append(f"fabricated reference (not in source): {ref}")
    if any(i.type.value == "empty_plan" for i in conformance.issues):
        blocking.append("the plan has no hubs")

    # ── things a human should look at → REVIEW ────────────────────────────────
    for issue in conformance.issues:
        if issue.type.value == "empty_plan":
            continue  # already blocking
        where = issue.object_name or "<plan>"
        review.append(f"convention: [{issue.type.value}] {where}: {issue.message}")

    if gold is not None:
        if gold.entity.false_negative > 0:
            review.append(
                f"missed {gold.entity.false_negative} expected entit"
                f"{'y' if gold.entity.false_negative == 1 else 'ies'} (vs the reference)"
            )
        if gold.entity.false_positive > 0:
            review.append(
                f"{gold.entity.false_positive} entit"
                f"{'y' if gold.entity.false_positive == 1 else 'ies'} not in the reference "
                "(possibly spurious)"
            )
        if gold.matched_entities > 0 and gold.naming_matches < gold.matched_entities:
            review.append(
                f"naming convention not followed on "
                f"{gold.matched_entities - gold.naming_matches}/{gold.matched_entities} entities"
            )
        if gold.produced_links > gold.expected_links:
            review.append(
                f"over-linking: {gold.produced_links} links produced vs "
                f"{gold.expected_links} expected"
            )
    else:
        review.append("no reference model for this system — correctness cannot be auto-verified")

    if blocking:
        verdict = ApprovalVerdict.REJECT
    elif review:
        verdict = ApprovalVerdict.REVIEW
    else:
        verdict = ApprovalVerdict.APPROVE

    return ApprovalRecommendation(
        verdict=verdict,
        blocking_reasons=tuple(blocking),
        review_reasons=tuple(review),
    )


__all__ = ["ApprovalRecommendation", "ApprovalVerdict", "recommend_approval"]
