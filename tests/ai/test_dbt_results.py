"""run_results.json parsing (gaps 2 & 3): model/test pass rates, compile signal."""

from __future__ import annotations

from dbt_builder.src.runners.dbt_results import classify, pass_rates

# A minimal but realistic run_results payload: 2 models built, 1 model errored,
# 3 tests (2 pass, 1 fail), 1 warn.
_MIXED = {
    "results": [
        {"unique_id": "model.p.hub_a", "status": "success"},
        {"unique_id": "model.p.hub_b", "status": "success"},
        {"unique_id": "model.p.sat_c", "status": "error"},
        {"unique_id": "test.p.not_null_hub_a_hk", "status": "pass"},
        {"unique_id": "test.p.unique_hub_a_hk", "status": "pass"},
        {"unique_id": "test.p.not_null_sat_c_ld", "status": "fail"},
        {"unique_id": "test.p.rel_hub_b", "status": "warn"},
    ]
}

_CLEAN_COMPILE = {
    "results": [
        {"unique_id": "model.p.hub_a", "status": "success"},
        {"unique_id": "model.p.hub_b", "status": "success"},
    ]
}


def test_classify_separates_models_and_tests():
    c = classify(_MIXED)
    assert c["model"] == {"success": 2, "error": 1}
    assert c["test"] == {"pass": 2, "fail": 1, "warn": 1}


def test_pass_rates_counts_and_ratios():
    r = pass_rates(_MIXED)
    assert r["models_total"] == 3
    assert r["models_success"] == 2
    assert r["models_error"] == 1
    assert r["tests_total"] == 4
    assert r["tests_passed"] == 2
    assert r["tests_failed"] == 1
    assert r["tests_warned"] == 1
    assert abs(r["test_pass_rate"] - 0.5) < 1e-9
    assert r["compiled_ok"] is False  # an error is present


def test_clean_compile_has_no_tests_and_is_ok():
    r = pass_rates(_CLEAN_COMPILE)
    assert r["compiled_ok"] is True
    assert r["models_success"] == 2
    # No tests executed on a compile → rate is None, not a misleading 0/1.
    assert r["test_pass_rate"] is None
    assert r["model_success_rate"] == 1.0


def test_empty_results_are_safe():
    r = pass_rates({"results": []})
    assert r["models_total"] == 0
    assert r["model_success_rate"] is None
    assert r["compiled_ok"] is True
