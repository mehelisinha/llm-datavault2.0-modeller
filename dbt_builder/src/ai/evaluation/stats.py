"""Statistical helpers: agreement, confidence intervals, consistency, idempotency.

Small, dependency-free implementations of the statistics the evaluation needs:

* :func:`cohens_kappa` — **chance-corrected agreement** between two label sets.
  Plain accuracy flatters a classifier when one class dominates; kappa subtracts
  the agreement expected by chance, so it is the honest number to report for the
  drift impact labels (and, given a second annotator, for gold-set inter-rater
  reliability).
* :func:`bootstrap_ci` — a **confidence interval** by resampling, so results are
  reported with dispersion rather than as bare point estimates. Non-parametric,
  which suits the very small samples here.
* :func:`plan_fingerprint` / :func:`self_consistency` — **output stability**: how
  often repeated generations from the same input agree on the same set of
  entities. A proxy for reliability (and for the model's own confidence).
* :func:`idempotency_rate` — the fraction of repeated runs that reproduce the
  first run's output **exactly**.

All pure and deterministic (the bootstrap takes an explicit seed).
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sequence

from dbt_builder.src.ai.contracts.decisions import ModelingPlan


def cohens_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """Cohen's kappa between two equal-length label sequences.

    ``1.0`` = perfect agreement, ``0.0`` = no better than chance, negative = worse
    than chance. Returns ``1.0`` when both raters used a single identical label
    (agreement is total and chance agreement is 1, an undefined 0/0 that is
    conventionally reported as perfect).
    """
    if len(a) != len(b):
        raise ValueError(f"label sequences differ in length: {len(a)} vs {len(b)}")
    n = len(a)
    if n == 0:
        raise ValueError("cannot compute kappa on empty label sequences")

    observed = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    count_a, count_b = Counter(a), Counter(b)
    expected = sum(
        (count_a[label] / n) * (count_b[label] / n)
        for label in set(count_a) | set(count_b)
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def bootstrap_ci(
    values: Sequence[float],
    *,
    confidence: float = 0.95,
    iterations: int = 10_000,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for the mean of ``values``.

    Deterministic for a fixed ``seed`` so reported intervals are reproducible.
    With a single observation the interval collapses to that value — reported
    honestly rather than implying precision that is not there.
    """
    if not values:
        raise ValueError("cannot bootstrap an empty sample")
    if len(values) == 1:
        return (float(values[0]), float(values[0]))
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(iterations):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    tail = (1.0 - confidence) / 2.0
    lo = means[int(tail * iterations)]
    hi = means[min(int((1.0 - tail) * iterations), iterations - 1)]
    return (round(lo, 4), round(hi, 4))


def plan_fingerprint(plan: ModelingPlan) -> tuple[tuple[str, ...], ...]:
    """Order-independent identity of a plan: its sorted hub / link / satellite names.

    The same fingerprint the modelling agent uses for majority voting, so
    consistency here is measured on the axis the pipeline itself cares about.
    """
    return (
        tuple(sorted(h.name.lower() for h in plan.hubs)),
        tuple(sorted(ln.name.lower() for ln in plan.links)),
        tuple(sorted(s.name.lower() for s in plan.satellites)),
    )


def self_consistency(plans: Sequence[ModelingPlan]) -> float:
    """Fraction of repeated generations sharing the **most common** fingerprint.

    ``1.0`` = every run produced the same entity set; ``1/n`` = all runs differed.
    Measures output stability independently of whether the output is *correct*.
    """
    if not plans:
        raise ValueError("cannot measure consistency of zero plans")
    counts = Counter(plan_fingerprint(p) for p in plans)
    return counts.most_common(1)[0][1] / len(plans)


def idempotency_rate(plans: Sequence[ModelingPlan]) -> float:
    """Fraction of runs reproducing the **first** run's plan exactly (field-for-field).

    Stricter than :func:`self_consistency`: it compares whole plans, not just the
    entity-name fingerprint, so a changed business key or payload counts as a
    difference.
    """
    if not plans:
        raise ValueError("cannot measure idempotency of zero plans")
    first = plans[0]
    return sum(1 for p in plans if p == first) / len(plans)


__all__ = [
    "bootstrap_ci",
    "cohens_kappa",
    "idempotency_rate",
    "plan_fingerprint",
    "self_consistency",
]
