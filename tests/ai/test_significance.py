"""Significance + effect-size helpers (gap 4: statistical power).

These are the statistics that upgrade the study from "means only" to means with a
permutation p-value and an effect size. The tests pin the exact-enumeration path
used at the real sample sizes (n=3–5), plus the boundary behaviours a small-n
test must get right: no effect, complete separation, and a hand-computable p-value.
"""

from __future__ import annotations

import math

from dbt_builder.src.ai.evaluation.stats import (
    cliffs_delta,
    cliffs_delta_label,
    compare_paired,
    paired_permutation_test,
)


def test_identical_samples_have_no_effect_and_p_one():
    a = [1.0, 1.0, 1.0]
    assert paired_permutation_test(a, list(a)) == 1.0
    assert cliffs_delta(a, list(a)) == 0.0
    assert cliffs_delta_label(0.0) == "negligible"


def test_exact_paired_p_value_is_hand_computable():
    # Three positive differences (1,1,1). Under sign-flips there are 2**3 = 8
    # equally likely sign assignments; the observed mean (all +) is the single
    # most-extreme outcome, tied only with the all-negative flip → 2/8 = 0.25.
    a = [1.0, 2.0, 3.0]
    b = [0.0, 1.0, 2.0]
    assert paired_permutation_test(a, b, alternative="two-sided") == 0.25
    # One-sided "greater" keeps only the all-positive flip → 1/8 = 0.125.
    assert paired_permutation_test(a, b, alternative="greater") == 0.125


def test_complete_separation_gives_delta_one():
    assert cliffs_delta([3.0, 4.0, 5.0], [0.0, 1.0, 2.0]) == 1.0
    assert cliffs_delta([0.0, 1.0], [3.0, 4.0]) == -1.0


def test_cliffs_delta_labels_follow_standard_bins():
    assert cliffs_delta_label(0.10) == "negligible"
    assert cliffs_delta_label(0.20) == "small"
    assert cliffs_delta_label(0.40) == "medium"
    assert cliffs_delta_label(0.90) == "large"


def test_compare_paired_bundles_effect_uncertainty_significance():
    # The CIM naming result recorded in findings §2.7: four seeds at 1.0 and one at
    # 0.333 (learning OFF) versus all five at 1.0 (learning ON).
    off = [1.0, 1.0, 1.0, 1.0, 1.0 / 3.0]
    on = [1.0, 1.0, 1.0, 1.0, 1.0]
    res = compare_paired(off, on)
    assert res["n_pairs"] == 5.0
    assert math.isclose(res["mean_a"], 0.8667, abs_tol=1e-3)
    assert res["mean_b"] == 1.0
    assert res["mean_diff"] < 0  # OFF is lower
    # Only one seed differs, so under sign-flips the effect is not significant
    # at n=5 — exactly the low-power point the thesis must be honest about.
    assert res["p_value"] > 0.05
    assert res["effect_size"] in {"negligible", "small", "medium", "large"}


def test_permutation_test_is_deterministic_in_montecarlo_regime():
    # Force the Monte-Carlo branch (n > max_exact) and confirm the fixed seed makes
    # it reproducible.
    a = [float(i) for i in range(25)]
    b = [float(i) + 0.5 for i in range(25)]
    p1 = paired_permutation_test(a, b, max_exact=10, iterations=5000, seed=7)
    p2 = paired_permutation_test(a, b, max_exact=10, iterations=5000, seed=7)
    assert p1 == p2
