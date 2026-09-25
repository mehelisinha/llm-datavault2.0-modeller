"""Tests for the dbt compile gate (hermetic — no real dbt / warehouse).

The dbt invocation is injected, so these exercise the full gate logic — phase
ordering, fail-closed misconfiguration, materialisation, and the approval-
blocking integration through ``validate()`` — without dbt-core or a connection.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ai

from dbt_builder.src.ai.validation import validate  # noqa: E402
from dbt_builder.src.ai.validation.dbt_gate import (  # noqa: E402
    DbtGateConfig,
    DbtOutcome,
    run_dbt_gate,
)

from ._factories import hub, plan, sat  # noqa: E402


def _plan():
    return plan(
        hubs=(hub("hub_terminal"),),
        satellites=(sat("sat_terminal_details", "hub_terminal"),),
    )


def _runner(*, failing: frozenset[str] = frozenset()):
    """A stub dbt runner that records the phases invoked and fails the named ones."""
    calls: list[str] = []

    def run(command: str, project_dir: str) -> DbtOutcome:
        calls.append(command)
        return DbtOutcome(command not in failing, f"{command} failed" if command in failing else "")

    run.calls = calls  # type: ignore[attr-defined]
    return run


def _project(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: test\n", encoding="utf-8")
    return str(tmp_path)


def _codes(issues):
    return [i.code for i in issues]


def test_disabled_gate_runs_nothing() -> None:
    runner = _runner()
    issues = run_dbt_gate(_plan(), None, config=DbtGateConfig(enabled=False), runner=runner)
    assert issues == []
    assert runner.calls == []


def test_enabled_without_project_dir_fails_closed() -> None:
    issues = run_dbt_gate(_plan(), None, config=DbtGateConfig(enabled=True, project_dir=""), runner=_runner())
    assert _codes(issues) == ["DBT_PROJECT_MISSING"]


def test_enabled_without_dbt_project_file_fails_closed(tmp_path) -> None:
    cfg = DbtGateConfig(enabled=True, project_dir=str(tmp_path))  # no dbt_project.yml written
    issues = run_dbt_gate(_plan(), None, config=cfg, runner=_runner())
    assert _codes(issues) == ["DBT_PROJECT_MISSING"]


def test_passing_gate_runs_parse_then_compile_and_materialises(tmp_path) -> None:
    cfg = DbtGateConfig(enabled=True, project_dir=_project(tmp_path))
    runner = _runner()
    issues = run_dbt_gate(_plan(), None, config=cfg, runner=runner)
    assert issues == []
    assert runner.calls == list(cfg.phases)  # exactly the configured phases, in order
    assert "build" not in cfg.phases  # build off by default
    # The generated model was written into the project for dbt to validate.
    assert (tmp_path / "models" / "raw_vault" / "hubs" / "hub_terminal.yml").is_file()


def test_parse_failure_blocks_and_skips_later_phases(tmp_path) -> None:
    cfg = DbtGateConfig(enabled=True, project_dir=_project(tmp_path))
    runner = _runner(failing=frozenset({"parse"}))
    issues = run_dbt_gate(_plan(), None, config=cfg, runner=runner)
    assert _codes(issues) == ["DBT_PARSE"]
    assert runner.calls == ["parse"]  # compile never attempted


def test_compile_failure_is_reported(tmp_path) -> None:
    cfg = DbtGateConfig(enabled=True, project_dir=_project(tmp_path))
    runner = _runner(failing=frozenset({"compile"}))
    issues = run_dbt_gate(_plan(), None, config=cfg, runner=runner)
    assert _codes(issues) == ["DBT_COMPILE"]
    assert runner.calls == ["parse", "compile"]


def test_build_phase_added_only_when_enabled(tmp_path) -> None:
    cfg = DbtGateConfig(enabled=True, project_dir=_project(tmp_path), run_build=True)
    runner = _runner()
    run_dbt_gate(_plan(), None, config=cfg, runner=runner)
    assert "build" in cfg.phases  # run_build adds the build phase
    assert runner.calls == list(cfg.phases)  # gate runs exactly the configured phases


def test_dbt_failure_blocks_approval_via_validate(tmp_path) -> None:
    # A dbt failure must make the overall report non-passing so approve() blocks.
    cfg = DbtGateConfig(enabled=True, project_dir=_project(tmp_path))
    report = validate(
        plan=_plan(),
        dbt_config=cfg,
        dbt_runner=_runner(failing=frozenset({"compile"})),
    )
    assert report.summary.errors >= 1
    assert report.passed is False
    assert "dbt_compile" in report.checks_run
