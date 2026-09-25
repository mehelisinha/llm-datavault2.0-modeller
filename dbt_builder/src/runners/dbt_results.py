"""Parse dbt's ``run_results.json`` into pass/fail rates (gaps 2 & 3).

dbt writes ``target/run_results.json`` after ``compile``/``run``/``test`` — a
machine-readable record of every node's status. This module turns that artifact
into the two numbers the thesis needs:

* **execution pass** (gap 2) — of the models dbt tried to *build*, how many
  succeeded, and of the data tests it ran, how many passed;
* **compile / structural-validity pass** (gap 3) — whether a project compiled
  with zero errors, aggregated across projects into a rate.

Pure and dependency-free: it classifies each result by the resource type encoded
in its ``unique_id`` (``model.…`` / ``test.…`` / ``seed.…``) and its status, so no
manifest or network is needed. Unit-tested on synthetic ``run_results`` payloads.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

# dbt status vocabularies differ by task: models build to success/error/skipped;
# data tests resolve to pass/fail/warn/error/skipped. Kept explicit so a new dbt
# status shows up as an unrecognised bucket rather than being silently miscounted.
_MODEL_OK = "success"
_TEST_OK = "pass"


def classify(run_results: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Count nodes by ``{resource_type: {status: n}}`` from a run_results payload.

    ``resource_type`` is the first dotted segment of ``unique_id`` (dbt's own
    convention), so models, tests, seeds and snapshots are separated without a
    manifest lookup.
    """
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for result in run_results.get("results", []):
        unique_id = str(result.get("unique_id", ""))
        resource_type = unique_id.split(".", 1)[0] or "unknown"
        status = str(result.get("status", "")).lower()
        out[resource_type][status] += 1
    return {rtype: dict(statuses) for rtype, statuses in out.items()}


def pass_rates(run_results: dict[str, Any]) -> dict[str, Any]:
    """Summarise a run_results payload into model- and test-level pass counts.

    ``*_rate`` is ``None`` when the denominator is zero (e.g. a ``compile`` run
    executes no tests), reported honestly rather than as a misleading ``0`` or
    ``1``. ``compiled_ok`` is true when no node errored — the structural-validity
    signal used for the compile-pass rate.
    """
    by_type = classify(run_results)
    models = by_type.get("model", {})
    tests = by_type.get("test", {})

    model_total = sum(models.values())
    model_ok = models.get(_MODEL_OK, 0)
    model_err = models.get("error", 0)
    test_total = sum(tests.values())
    test_ok = tests.get(_TEST_OK, 0)
    test_fail = tests.get("fail", 0) + tests.get("error", 0)

    any_error = any(
        s in ("error", "fail") and n
        for statuses in by_type.values()
        for s, n in statuses.items()
    )
    return {
        "models_total": model_total,
        "models_success": model_ok,
        "models_error": model_err,
        "model_success_rate": (model_ok / model_total) if model_total else None,
        "tests_total": test_total,
        "tests_passed": test_ok,
        "tests_failed": test_fail,
        "tests_warned": tests.get("warn", 0),
        "test_pass_rate": (test_ok / test_total) if test_total else None,
        "compiled_ok": not any_error,
        "by_type": by_type,
    }


__all__ = ["classify", "pass_rates"]
