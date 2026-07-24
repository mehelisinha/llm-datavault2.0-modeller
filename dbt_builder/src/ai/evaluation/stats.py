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
* :func:`paired_permutation_test` / :func:`cliffs_delta` / :func:`compare_paired`
  — **significance and effect size** for the tiny, paired seed samples used in the
  experiments. A permutation test is exact for small n and makes no normality
  assumption (a t-test would be indefensible at n=3–5); Cliff's delta reports the
  *size* of a difference independently of whether it is significant; and both are
  bundled by :func:`compare_paired` alongside the mean difference and its bootstrap
  interval, so a comparison is never reported as a bare pair of means.

All pure and deterministic (every resampling routine takes an explicit seed).
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sequence
from itertools import product

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


def _is_extreme(candidate: float, observed: float, alternative: str) -> bool:
    """Whether a permuted statistic is at least as extreme as ``observed``."""
    if alternative == "two-sided":
        return abs(candidate) >= abs(observed) - 1e-12
    if alternative == "greater":
        return candidate >= observed - 1e-12
    if alternative == "less":
        return candidate <= observed + 1e-12
    raise ValueError(f"unknown alternative: {alternative!r}")


def paired_permutation_test(
    a: Sequence[float],
    b: Sequence[float],
    *,
    alternative: str = "two-sided",
    max_exact: int = 18,
    iterations: int = 100_000,
    seed: int = 0,
) -> float:
    """Permutation p-value that the paired mean difference ``mean(a - b)`` is zero.

    The experiments pair conditions by seed (``off@42`` vs ``on@42``), so the
    correct test is a **paired** one: it permutes by flipping the sign of each
    per-pair difference — the exact null for "the condition label is exchangeable
    within a pair". No normality assumption, which a t-test could not justify at
    n=3–5.

    Exhaustively enumerates all ``2**n`` sign-flips when ``n <= max_exact`` (an
    *exact* p-value); otherwise Monte-Carlo samples ``iterations`` flips with a
    fixed ``seed`` (reproducible). Returns ``1.0`` when every difference is zero
    (no effect to detect).
    """
    if len(a) != len(b):
        raise ValueError(f"paired samples differ in length: {len(a)} vs {len(b)}")
    n = len(a)
    if n == 0:
        raise ValueError("cannot test empty samples")

    diffs = [float(x) - float(y) for x, y in zip(a, b, strict=True)]
    if all(abs(d) <= 1e-12 for d in diffs):
        return 1.0
    observed = sum(diffs) / n

    if n <= max_exact:
        total = 0
        extreme = 0
        for signs in product((1.0, -1.0), repeat=n):
            stat = sum(s * d for s, d in zip(signs, diffs, strict=True)) / n
            total += 1
            if _is_extreme(stat, observed, alternative):
                extreme += 1
        return extreme / total

    rng = random.Random(seed)
    extreme = 0
    for _ in range(iterations):
        stat = sum((d if rng.random() < 0.5 else -d) for d in diffs) / n
        if _is_extreme(stat, observed, alternative):
            extreme += 1
    return extreme / iterations


def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> float:
    """Cliff's delta effect size: P(a>b) − P(a<b), in ``[-1, 1]``.

    A non-parametric, scale-free measure of *how much* two samples differ, robust
    to the tiny n here. ``0`` = fully overlapping, ``±1`` = complete separation.
    Report it beside the permutation p-value so a "non-significant" result at low
    power is not mistaken for "no effect", and a significant one carries its size.
    """
    if not a or not b:
        raise ValueError("cannot compute Cliff's delta on an empty sample")
    gt = sum(1 for x in a for y in b if x > y)
    lt = sum(1 for x in a for y in b if x < y)
    return (gt - lt) / (len(a) * len(b))


def cliffs_delta_label(delta: float) -> str:
    """Standard magnitude bins for Cliff's delta (Romano et al., 2006)."""
    d = abs(delta)
    if d < 0.147:
        return "negligible"
    if d < 0.330:
        return "small"
    if d < 0.474:
        return "medium"
    return "large"


def compare_paired(
    a: Sequence[float],
    b: Sequence[float],
    *,
    alternative: str = "two-sided",
    seed: int = 0,
) -> dict[str, float | str]:
    """Full paired comparison of two conditions: means, difference, CI, p, effect.

    Bundles :func:`paired_permutation_test`, :func:`cliffs_delta` and a bootstrap
    interval on the per-pair differences so a contrast is reported as *effect +
    uncertainty + significance*, never as two bare means. Deterministic for a
    fixed ``seed``.
    """
    n = len(a)
    diffs = [float(x) - float(y) for x, y in zip(a, b, strict=True)]
    mean_a = sum(a) / n if n else 0.0
    mean_b = sum(b) / n if n else 0.0
    lo, hi = bootstrap_ci(diffs, seed=seed) if n else (0.0, 0.0)
    delta = cliffs_delta(a, b)
    return {
        "n_pairs": float(n),
        "mean_a": round(mean_a, 4),
        "mean_b": round(mean_b, 4),
        "mean_diff": round(mean_a - mean_b, 4),
        "diff_ci_low": lo,
        "diff_ci_high": hi,
        "p_value": round(paired_permutation_test(a, b, alternative=alternative, seed=seed), 4),
        "cliffs_delta": round(delta, 4),
        "effect_size": cliffs_delta_label(delta),
    }


__all__ = [
    "bootstrap_ci",
    "cliffs_delta",
    "cliffs_delta_label",
    "cohens_kappa",
    "compare_paired",
    "idempotency_rate",
    "paired_permutation_test",
    "plan_fingerprint",
    "self_consistency",
]
