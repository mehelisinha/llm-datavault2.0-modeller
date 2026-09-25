"""dbt compile gate — proves a generated plan materialises into a buildable
AutomateDV project before it can be approved.

The AI pipeline emits *metadata*; this gate writes that metadata out as the
per-object dbt model YAMLs (via :class:`YamlGenerator`) into a configured dbt
project, then runs ``dbt parse`` → ``dbt compile`` (and ``dbt build`` when
sample data is available). Any dbt failure is surfaced as an ERROR
:class:`ValidationIssue`, which the approval gate treats as blocking — so a
plan is only approvable/exportable if it genuinely compiles.

The dbt invocation is injected (:data:`DbtCommandRunner`) so the gate logic is
fully unit-testable without dbt-core, a warehouse connection, or network. The
project must have AutomateDV installed (``dbt deps``) and a usable profile for
the real runner to succeed; the gate is OFF unless explicitly enabled.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from dbt_builder.src.ai.agents.yaml_generator import (
    BUSINESS_VAULT_ROOT,
    RAW_VAULT_ROOT,
    YamlGenerator,
)
from dbt_builder.src.ai.contracts.validation import Severity, ValidationIssue

if TYPE_CHECKING:
    from dbt_builder.src.ai.contracts.bv import BvProposal
    from dbt_builder.src.ai.contracts.decisions import ModelingPlan
    from dbt_builder.src.ai.settings import AISettings

# Ordered dbt phases. ``parse`` + ``compile`` are the always-required gate;
# ``build`` is opt-in and only meaningful when the project can reach data.
_REQUIRED_PHASES: tuple[str, ...] = ("parse", "compile")
_BUILD_PHASE = "build"

_DBT_PROJECT_FILE = "dbt_project.yml"


@dataclass(frozen=True)
class DbtOutcome:
    """Result of one dbt command invocation."""

    success: bool
    detail: str = ""


# (command, project_dir) -> outcome. Injected so tests need no real dbt.
DbtCommandRunner = Callable[[str, str], DbtOutcome]


@dataclass(frozen=True)
class DbtGateConfig:
    """Whether/where/how hard to run the dbt gate (sourced from settings)."""

    enabled: bool = False
    project_dir: str = ""
    run_build: bool = False

    @classmethod
    def from_settings(cls, settings: AISettings) -> DbtGateConfig:
        return cls(
            enabled=bool(getattr(settings, "dbt_validation_enabled", False)),
            project_dir=str(getattr(settings, "dbt_project_dir", "") or ""),
            run_build=bool(getattr(settings, "dbt_build_enabled", False)),
        )

    @property
    def phases(self) -> tuple[str, ...]:
        """The dbt phases to run, in dependency order."""
        return (*_REQUIRED_PHASES, _BUILD_PHASE) if self.run_build else _REQUIRED_PHASES


def _default_runner(command: str, project_dir: str) -> DbtOutcome:
    """Invoke a dbt command via dbt-core; any failure becomes a non-success."""
    try:
        from dbt.cli.main import dbtRunner
    except Exception as exc:  # noqa: BLE001 — dbt-core not importable in this env
        return DbtOutcome(False, f"dbt-core is not available: {exc}")
    try:
        result = dbtRunner().invoke([command, "--project-dir", project_dir])
    except Exception as exc:  # noqa: BLE001 — invocation raised
        return DbtOutcome(False, f"dbt {command} raised: {exc}")
    return DbtOutcome(
        bool(getattr(result, "success", False)),
        str(getattr(result, "exception", "") or ""),
    )


def _materialise(plan: ModelingPlan, bv: BvProposal | None, project: Path) -> None:
    """Write the plan's per-object model YAMLs into the project.

    The generator's output directories are cleared first so only the current
    plan's models are validated (no stale models from a previous generation).
    """
    for generated_root in (RAW_VAULT_ROOT, BUSINESS_VAULT_ROOT):
        shutil.rmtree(project / generated_root, ignore_errors=True)
    generator = YamlGenerator()
    generator.write_to_disk(generator.render(plan=plan, bv=bv), project)


def _error(code: str, message: str, project_dir: str, suggestion: str | None = None) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=Severity.ERROR,
        message=message,
        location=project_dir or None,
        suggestion=suggestion,
    )


def run_dbt_gate(
    plan: ModelingPlan | None,
    bv: BvProposal | None = None,
    *,
    config: DbtGateConfig,
    runner: DbtCommandRunner | None = None,
) -> list[ValidationIssue]:
    """Materialise ``plan`` into the configured dbt project and run the gate.

    Returns ERROR issues for the first failing phase (later phases depend on
    earlier ones, so the run stops at the first failure). Returns ``[]`` when
    the gate is disabled or there is no plan to materialise. When enabled but
    misconfigured (no project dir / missing ``dbt_project.yml``) it fails
    closed with an ERROR — an enabled gate that cannot run must not silently
    pass a plan as approvable.
    """
    if not config.enabled:
        return []
    if plan is None:
        return []
    run = runner or _default_runner

    if not config.project_dir:
        return [_error("DBT_PROJECT_MISSING", "dbt validation is enabled but no dbt_project_dir is configured.", "")]
    project = Path(config.project_dir)
    if not (project / _DBT_PROJECT_FILE).is_file():
        return [
            _error(
                "DBT_PROJECT_MISSING",
                f"No {_DBT_PROJECT_FILE} found under configured dbt_project_dir '{config.project_dir}'.",
                config.project_dir,
                "Point dbt_project_dir at an AutomateDV dbt project (with deps installed).",
            )
        ]

    try:
        _materialise(plan, bv, project)
    except Exception as exc:  # noqa: BLE001 — surface a materialisation failure as ERROR
        return [
            _error(
                "DBT_MATERIALISE",
                f"Failed to write generated models into the dbt project: {exc}",
                config.project_dir,
            )
        ]

    issues: list[ValidationIssue] = []
    for phase in config.phases:
        outcome = run(phase, str(project))
        if not outcome.success:
            issues.append(
                _error(
                    f"DBT_{phase.upper()}",
                    f"dbt {phase} failed: {outcome.detail or 'see dbt logs'}",
                    config.project_dir,
                    "Fix the generated model definitions or the dbt project setup (dbt deps, profiles).",
                )
            )
            break  # downstream phases depend on this one — don't run them
    return issues
