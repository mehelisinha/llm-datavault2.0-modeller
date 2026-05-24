"""Pipeline orchestration: sequences the six pipeline steps into a single run.

Design
------
* Imports step-level modules (``ai.pipeline``, ``ai.agents``, ``ai.rendering``)
  the same way :class:`DwaService` does — never through the service facade —
  to avoid a circular import.
* Every step is wrapped in try/except that converts any exception into a
  ``PipelineStepResult(status='failed')``.  The run becomes FAILED immediately
  and no further steps are attempted.
* :class:`PipelineRun` is updated *functionally*: each step returns a new
  instance via ``model_copy(update={…})``.
* The :class:`~dbt_builder.src.ai.supervision.PipelineSupervisor` is consulted
  after SNAPSHOT, ARCHITECT_BV and VALIDATE.  When it recommends PAUSE and the
  caller has not set ``acknowledge_risks=True`` the run halts with
  ``status=PAUSED`` and the assessment is attached for UI display.
* External callers never need to know about ``stop_after`` — that flag is kept
  for tests and the supervisor's internal logic.  The public surface is one
  call: "run the pipeline; surface risks; produce YAML for human approval".
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from dbt_builder.src.ai.contracts.pipeline_run import (
    PipelineRun,
    PipelineRunStatus,
    PipelineStepName,
    PipelineStepResult,
    StopAfter,
)
from dbt_builder.src.ai.contracts.supervision import (
    RiskAssessment,
    SupervisionRecommendation,
)
from dbt_builder.src.ai.pipeline import bronze_reader, catalog_inspector, diff_analyzer
from dbt_builder.src.ai.rendering.metadata_v3_emitter import render_v3

if TYPE_CHECKING:
    from dbt_builder.src.ai.agents import BvArchitect, SchemaAnalyzer, YamlGenerator
    from dbt_builder.src.ai.supervision import PipelineSupervisor

_LOG = logging.getLogger(__name__)


# ── Input bundle ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PipelineInput:
    """Bundled inputs for a full pipeline run.

    Groups request parameters (catalog, schema names, system metadata) and
    environment-injected catalog callables (stub or Spark).  A stdlib
    dataclass is used because callables cannot be JSON-serialised —
    ``PipelineInput`` is an in-process transport, not a wire contract.
    """

    catalog: str
    bronze_schema: str
    vault_schema: str
    system: object  # SourceSystem; typed as object to avoid an import cycle
    list_vault_entities: catalog_inspector.ListEntities
    describe_vault: catalog_inspector.DescribeTable
    list_bronze_tables: bronze_reader.ListTables
    describe_bronze: bronze_reader.DescribeTable

    metadata_yaml_path: str | None = None
    include_patterns: tuple[str, ...] = field(default_factory=tuple)
    exclude_patterns: tuple[str, ...] = field(default_factory=tuple)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _elapsed_ms(t0: float) -> int:
    return max(0, int((time.perf_counter() - t0) * 1000))


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Orchestrator ─────────────────────────────────────────────────────────────


class PipelineOrchestrator:
    """Execute the DWA pipeline steps in sequence.

    Parameters
    ----------
    schema_analyzer
        LLM-backed analyzer for Step 4 (ANALYZE).  When ``None`` the step
        fails gracefully with an informative error rather than raising.
    bv_architect
        BV Architect for Step 4b. Defaults to a new ``BvArchitect()``.
    yaml_generator
        YAML Generator for Step 5. Defaults to a new ``YamlGenerator()``.
    supervisor
        Risk-based supervisor.  When ``None`` (or disabled per-run via
        ``acknowledge_risks=True``) the run never pauses.  Default is
        ``PipelineSupervisor()``.
    """

    def __init__(
        self,
        *,
        schema_analyzer: SchemaAnalyzer | None = None,
        bv_architect: BvArchitect | None = None,
        yaml_generator: YamlGenerator | None = None,
        supervisor: PipelineSupervisor | None = None,
    ) -> None:
        from dbt_builder.src.ai.agents import BvArchitect, YamlGenerator
        from dbt_builder.src.ai.supervision import PipelineSupervisor

        self._schema_analyzer = schema_analyzer
        self._bv_architect = bv_architect or BvArchitect()
        self._yaml_generator = yaml_generator or YamlGenerator()
        self._supervisor = supervisor if supervisor is not None else PipelineSupervisor()

    # ── Public entrypoint ────────────────────────────────────────────────────

    def run(
        self,
        pipeline_input: PipelineInput,
        *,
        stop_after: StopAfter | None = None,
        run_id: str | None = None,
        acknowledge_risks: bool = False,
    ) -> PipelineRun:
        """Execute the pipeline, returning the final :class:`PipelineRun`.

        Parameters
        ----------
        stop_after
            Internal checkpoint for tests / supervisor; the agentic UI does
            not surface this.
        acknowledge_risks
            When True the supervisor's PAUSE recommendation is downgraded to
            an informational annotation — the run continues to YAML.  Used
            when the operator clicks "Continue anyway" after reviewing the
            risk banner.
        """
        now = _now()
        run = PipelineRun(
            run_id=run_id or str(uuid.uuid4()),
            status=PipelineRunStatus.RUNNING,
            stop_after=stop_after,
            created_at=now,
            updated_at=now,
        )

        # ── SNAPSHOT ─────────────────────────────────────────────────────────
        run, failed = self._do_snapshot(run, pipeline_input)
        if failed:
            return run
        run, paused = self._maybe_pause(run, PipelineStepName.SNAPSHOT, acknowledge_risks)
        if paused:
            return run
        if stop_after is StopAfter.DIFF:
            return _pause(run)

        # ── ANALYZE ──────────────────────────────────────────────────────────
        run, failed = self._do_analyze(run, pipeline_input)
        if failed:
            return run

        # ── ARCHITECT_BV ─────────────────────────────────────────────────────
        run, failed = self._do_architect_bv(run)
        if failed:
            return run
        run, paused = self._maybe_pause(run, PipelineStepName.ARCHITECT_BV, acknowledge_risks)
        if paused:
            return run
        if stop_after is StopAfter.PLAN:
            return _pause(run)

        # ── GENERATE ─────────────────────────────────────────────────────────
        run, failed = self._do_generate(run)
        if failed:
            return run

        # ── VALIDATE ─────────────────────────────────────────────────────────
        run, failed = self._do_validate(run)
        if failed:
            return run
        run, paused = self._maybe_pause(run, PipelineStepName.VALIDATE, acknowledge_risks)
        if paused:
            return run
        if stop_after is StopAfter.YAML:
            return _pause(run)

        return run.model_copy(update={"status": PipelineRunStatus.DONE, "updated_at": _now()})

    # ── Supervisor helper ────────────────────────────────────────────────────

    def _maybe_pause(
        self,
        run: PipelineRun,
        after_step: PipelineStepName,
        acknowledge_risks: bool,
    ) -> tuple[PipelineRun, bool]:
        """Consult the supervisor; pause the run if PAUSE is recommended.

        When ``acknowledge_risks`` is True the assessment is still attached
        (so the UI can keep showing the banner) but the run continues.
        """
        assessment: RiskAssessment | None = self._supervisor.evaluate(run, after_step=after_step)
        if assessment is None:
            return run, False

        updated = run.model_copy(update={"risk_assessment": assessment, "updated_at": _now()})
        if assessment.recommendation is SupervisionRecommendation.PAUSE and not acknowledge_risks:
            return (
                updated.model_copy(
                    update={"status": PipelineRunStatus.PAUSED, "updated_at": _now()}
                ),
                True,
            )
        return updated, False

    # ── Step implementations ─────────────────────────────────────────────────

    def _do_snapshot(self, run: PipelineRun, pi: PipelineInput) -> tuple[PipelineRun, bool]:
        t0 = time.perf_counter()
        try:
            catalog_snapshot = catalog_inspector.inspect_catalog(
                catalog=pi.catalog,
                schema_name=pi.vault_schema,
                list_entities=pi.list_vault_entities,
                describe_table=pi.describe_vault,
                metadata_yaml_path=pi.metadata_yaml_path,
            )
            bronze_snapshot = bronze_reader.read_bronze(
                catalog=pi.catalog,
                schema_name=pi.bronze_schema,
                list_tables=pi.list_bronze_tables,
                describe_table=pi.describe_bronze,
                include_patterns=pi.include_patterns,
                exclude_patterns=pi.exclude_patterns,
            )
            change_set = diff_analyzer.diff(catalog_snapshot, bronze_snapshot)
        except Exception as exc:
            return self._fail(run, PipelineStepName.SNAPSHOT, t0, exc)

        step = PipelineStepResult(
            step=PipelineStepName.SNAPSHOT, status="ok", duration_ms=_elapsed_ms(t0)
        )
        return run.model_copy(
            update={
                "system": pi.system,
                "catalog_snapshot": catalog_snapshot,
                "bronze_snapshot": bronze_snapshot,
                "change_set": change_set,
                "steps": (*run.steps, step),
                "updated_at": _now(),
            }
        ), False

    def _do_analyze(self, run: PipelineRun, pi: PipelineInput) -> tuple[PipelineRun, bool]:
        t0 = time.perf_counter()
        if self._schema_analyzer is None:
            exc = RuntimeError(
                "SchemaAnalyzer is not configured. "
                "Pass schema_analyzer= when constructing DwaService or PipelineOrchestrator."
            )
            return self._fail(run, PipelineStepName.ANALYZE, t0, exc)
        try:
            assert run.bronze_snapshot is not None, "bronze_snapshot missing before ANALYZE"
            assert run.change_set is not None, "change_set missing before ANALYZE"
            from dbt_builder.src.ai.contracts.payloads import SourceSystem

            system: SourceSystem = pi.system  # type: ignore[assignment]
            plan = self._schema_analyzer.analyze(
                system=system,
                bronze=run.bronze_snapshot,
                change_set=run.change_set,
                catalog_snapshot=run.catalog_snapshot,
            )
        except Exception as exc:
            return self._fail(run, PipelineStepName.ANALYZE, t0, exc)

        step = PipelineStepResult(
            step=PipelineStepName.ANALYZE, status="ok", duration_ms=_elapsed_ms(t0)
        )
        return run.model_copy(
            update={"plan": plan, "steps": (*run.steps, step), "updated_at": _now()}
        ), False

    def _do_architect_bv(self, run: PipelineRun) -> tuple[PipelineRun, bool]:
        t0 = time.perf_counter()
        try:
            assert run.plan is not None, "plan missing before ARCHITECT_BV"
            bv = self._bv_architect.propose(run.plan)
        except Exception as exc:
            return self._fail(run, PipelineStepName.ARCHITECT_BV, t0, exc)

        step = PipelineStepResult(
            step=PipelineStepName.ARCHITECT_BV, status="ok", duration_ms=_elapsed_ms(t0)
        )
        return run.model_copy(
            update={"bv": bv, "steps": (*run.steps, step), "updated_at": _now()}
        ), False

    def _do_generate(self, run: PipelineRun) -> tuple[PipelineRun, bool]:
        t0 = time.perf_counter()
        try:
            assert run.plan is not None, "plan missing before GENERATE"
            assert run.system is not None, "system missing before GENERATE"
            from dbt_builder.src.ai.contracts.payloads import SourceSystem

            system: SourceSystem = run.system  # type: ignore[assignment]
            rendered_yaml = render_v3(plan=run.plan, system=system, bv=run.bv)
        except Exception as exc:
            return self._fail(run, PipelineStepName.GENERATE, t0, exc)

        step = PipelineStepResult(
            step=PipelineStepName.GENERATE, status="ok", duration_ms=_elapsed_ms(t0)
        )
        return run.model_copy(
            update={
                "rendered_yaml": rendered_yaml,
                "steps": (*run.steps, step),
                "updated_at": _now(),
            }
        ), False

    def _do_validate(self, run: PipelineRun) -> tuple[PipelineRun, bool]:
        from dbt_builder.src.ai.validation import validate as run_validation

        t0 = time.perf_counter()
        try:
            validation = run_validation(
                plan=run.plan,
                rendered_yaml=run.rendered_yaml,
            )
        except Exception as exc:
            return self._fail(run, PipelineStepName.VALIDATE, t0, exc)

        step = PipelineStepResult(
            step=PipelineStepName.VALIDATE, status="ok", duration_ms=_elapsed_ms(t0)
        )
        return run.model_copy(
            update={
                "validation": validation,
                "steps": (*run.steps, step),
                "updated_at": _now(),
            }
        ), False

    # ── Error helper ─────────────────────────────────────────────────────────

    @staticmethod
    def _fail(
        run: PipelineRun,
        step_name: PipelineStepName,
        t0: float,
        exc: Exception,
    ) -> tuple[PipelineRun, bool]:
        _LOG.exception("Pipeline step %s failed: %s", step_name.value, exc)
        step = PipelineStepResult(
            step=step_name,
            status="failed",
            duration_ms=_elapsed_ms(t0),
            error=str(exc),
        )
        return run.model_copy(
            update={
                "status": PipelineRunStatus.FAILED,
                "steps": (*run.steps, step),
                "error_detail": str(exc),
                "updated_at": _now(),
            }
        ), True


def _pause(run: PipelineRun) -> PipelineRun:
    return run.model_copy(update={"status": PipelineRunStatus.PAUSED, "updated_at": _now()})
