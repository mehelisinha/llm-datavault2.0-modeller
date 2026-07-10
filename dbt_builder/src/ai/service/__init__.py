"""Service facade: the *only* surface the API and UI may import.

Why a facade
------------
The architecture test (``tests/ai/test_architecture.py``) is being extended
to forbid the API / UI layers from reaching directly into ``ai.agents``,
``ai.pipeline``, ``ai.discovery``, ``ai.rendering`` or ``ai.embeddings``.
Routing every call through this facade means:

* every UI path is testable without spinning up FastAPI;
* refactors inside ``ai/*`` cannot accidentally break the UI;
* guardrails (validation, approval gate) can never be bypassed by a
  caller that imports an internal helper directly.

This module is intentionally thin: it composes the deterministic Steps 1-3,
the Validator (Step 6), and the approval store. LLM agents (Steps 4, 4b, 5)
are wired in during Phase B; the facade exposes stable method signatures
now so the API can be built against them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dbt_builder.src.ai.agents import (
    BvArchitect,
    SchemaAnalyzer,
    YamlBundle,
    YamlGenerator,
)
from dbt_builder.src.ai.contracts.approval import ApprovalRecord, ApprovalStatus
from dbt_builder.src.ai.contracts.bv import BvProposal
from dbt_builder.src.ai.contracts.catalog import (
    BronzeSnapshot,
    CatalogSnapshot,
    ChangeSet,
)
from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.contracts.payloads import SourceSystem
from dbt_builder.src.ai.contracts.pipeline_run import (
    PipelineRun,
    PipelineRunStatus,
    PipelineStepName,
    PipelineStepResult,
    StopAfter,
)
from dbt_builder.src.ai.contracts.supervision import (
    RiskAssessment,
    RiskKind,
    RiskSeverity,
    RiskSignal,
    SupervisionRecommendation,
)
from dbt_builder.src.ai.contracts.validation import ValidationReport
from dbt_builder.src.ai.orchestration import PipelineInput, PipelineOrchestrator
from dbt_builder.src.ai.pipeline import bronze_reader, catalog_inspector, diff_analyzer
from dbt_builder.src.ai.store import (
    ApprovalStore,
    SqliteApprovalStore,
    make_record,
)
from dbt_builder.src.ai.store.corpus import make_example_store, plan_to_example_rows
from dbt_builder.src.ai.store.pipeline_run_store import (
    InMemoryPipelineRunStore,
    PipelineRunStore,
    get_pipeline_run_store,
    set_pipeline_run_store,
)
from dbt_builder.src.ai.store.yaml_store import (
    LocalYamlStore,
    YamlStore,
    catalog_from_yaml,
    make_yaml_store,
)
from dbt_builder.src.ai.supervision import PipelineSupervisor, SupervisorConfig
from dbt_builder.src.ai.validation import validate as run_validation

if TYPE_CHECKING:
    from dbt_builder.src.utils.yaml_store import DeltaExampleStore


class ApprovalGateError(RuntimeError):
    """Raised when a caller tries to approve a plan that has ERROR-severity issues."""


class LlmAgentNotConfiguredError(RuntimeError):
    """Raised when an LLM-backed agent (SchemaAnalyzer) is invoked without being wired.

    The deterministic agents (BvArchitect, YamlGenerator) always have safe
    defaults; the SchemaAnalyzer needs an Azure OpenAI client and so cannot
    be defaulted without a credential. Callers (the API) translate this to
    HTTP 503.
    """


class DwaService:
    """High-level orchestration entry point used by the API."""

    def __init__(
        self,
        *,
        approval_store: ApprovalStore | None = None,
        schema_analyzer: SchemaAnalyzer | None = None,
        bv_architect: BvArchitect | None = None,
        yaml_generator: YamlGenerator | None = None,
        pipeline_run_store: PipelineRunStore | None = None,
        supervisor: PipelineSupervisor | None = None,
        yaml_store: YamlStore | None = None,
        example_store: DeltaExampleStore | None = None,
    ) -> None:
        self._store: ApprovalStore = approval_store or SqliteApprovalStore(
            Path(".cache") / "approvals.sqlite"
        )
        # Optional — analyze() raises LlmAgentNotConfiguredError if missing.
        self._schema_analyzer = schema_analyzer
        # Deterministic agents always have safe defaults.
        self._bv_architect = bv_architect or BvArchitect()
        self._yaml_generator = yaml_generator or YamlGenerator()
        # Pipeline run history (in-memory by default).
        self._pipeline_run_store: PipelineRunStore = pipeline_run_store or get_pipeline_run_store()
        # Default supervisor; override at construction time for custom thresholds.
        self._supervisor = supervisor if supervisor is not None else PipelineSupervisor()
        # YAML metadata store — local dev fallback until ADLS settings are provided.
        if yaml_store is not None:
            self._yaml_store: YamlStore = yaml_store
        else:
            try:
                from dbt_builder.src.ai.settings import get_settings

                self._yaml_store = make_yaml_store(get_settings())
            except Exception:
                self._yaml_store = LocalYamlStore()
        # Learning corpus (feedback loop) — Delta-only; stays None on local / CI
        # (or any construction failure) so approval NEVER depends on a warehouse
        # being reachable. Populated on approve() alongside the YAML store.
        if example_store is not None:
            self._example_store: DeltaExampleStore | None = example_store
        else:
            try:
                from dbt_builder.src.ai.settings import get_settings

                self._example_store = make_example_store(get_settings())
            except Exception:
                self._example_store = None

    # ── Step 1 ──────────────────────────────────────────────────────────────
    def inspect_catalog(
        self,
        *,
        catalog: str,
        schema_name: str,
        list_entities: catalog_inspector.ListEntities,
        describe_table: catalog_inspector.DescribeTable,
        metadata_yaml_path: str | Path | None = None,
        describe_parallelism: int | None = None,
    ) -> CatalogSnapshot:
        return catalog_inspector.inspect_catalog(
            catalog=catalog,
            schema_name=schema_name,
            list_entities=list_entities,
            describe_table=describe_table,
            metadata_yaml_path=metadata_yaml_path,
            describe_parallelism=self._resolve_describe_parallelism(describe_parallelism),
        )

    # ── Step 2 ──────────────────────────────────────────────────────────────
    def read_bronze(
        self,
        *,
        catalog: str,
        schema_name: str,
        list_tables: bronze_reader.ListTables,
        describe_table: bronze_reader.DescribeTable,
        include_patterns: tuple[str, ...] = (),
        exclude_patterns: tuple[str, ...] = (),
        describe_parallelism: int | None = None,
    ) -> BronzeSnapshot:
        return bronze_reader.read_bronze(
            catalog=catalog,
            schema_name=schema_name,
            list_tables=list_tables,
            describe_table=describe_table,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            describe_parallelism=self._resolve_describe_parallelism(describe_parallelism),
        )

    def _resolve_describe_parallelism(self, override: int | None) -> int:
        """Return the effective ``describe_table`` concurrency.

        Centralised so both Step 1 and Step 2 read the same setting and
        callers can still pin a value per request (e.g. for debugging).
        """
        if override is not None:
            return override
        try:
            from dbt_builder.src.ai.settings import get_settings

            return get_settings().catalog_describe_parallelism
        except Exception:
            # Settings are misconfigured (no Azure creds in unit tests etc.);
            # fall back to the legacy serial behaviour rather than crashing.
            return 1

    # ── Step 3 ──────────────────────────────────────────────────────────────
    def diff(self, catalog: CatalogSnapshot, bronze: BronzeSnapshot) -> ChangeSet:
        return diff_analyzer.diff(catalog, bronze)

    # ── Step 4 (LLM) ─────────────────────────────────────────────────────────────────
    def analyze(
        self,
        *,
        system: SourceSystem,
        bronze: BronzeSnapshot,
        change_set: ChangeSet,
    ) -> ModelingPlan:
        """Step 4 — SchemaAnalyzer agent. Requires an LLM-bound analyzer."""
        if self._schema_analyzer is None:
            raise LlmAgentNotConfiguredError(
                "DwaService was constructed without a SchemaAnalyzer; "
                "bind one (DwaService(schema_analyzer=...)) before calling analyze()."
            )
        return self._schema_analyzer.analyze(system=system, bronze=bronze, change_set=change_set)

    # ── Step 4b ──────────────────────────────────────────────────────────────────────
    def architect_bv(self, plan: ModelingPlan) -> BvProposal:
        """Step 4b — BV Architect; deterministic, always available."""
        return self._bv_architect.propose(plan)

    # ── Step 5 ──────────────────────────────────────────────────────────────────────
    def generate_yaml(
        self,
        *,
        plan: ModelingPlan,
        bv: BvProposal | None = None,
    ) -> YamlBundle:
        """Step 5 — YAML Generator; deterministic, always available."""
        return self._yaml_generator.render(plan=plan, bv=bv)

    # ── Step 6 ──────────────────────────────────────────────────────────────
    def validate(
        self,
        *,
        plan: ModelingPlan | None = None,
        rendered_yaml: str | None = None,
        bv: BvProposal | None = None,
    ) -> ValidationReport:
        """Validate a plan/YAML, including the dbt compile gate when enabled.

        The dbt gate config is read from settings (disabled by default), so the
        same call both unit-tests offline and enforces compilation in a
        configured environment — nothing approvable unless dbt parse/compile pass.
        """
        from dbt_builder.src.ai.validation.dbt_gate import DbtGateConfig

        try:
            from dbt_builder.src.ai.settings import get_settings

            dbt_config = DbtGateConfig.from_settings(get_settings())
        except Exception:  # noqa: BLE001 — settings unconfigured (offline/tests)
            dbt_config = DbtGateConfig()
        return run_validation(
            plan=plan,
            rendered_yaml=rendered_yaml,
            bv=bv,
            dbt_config=dbt_config,
        )

    # ── Approval gate ───────────────────────────────────────────────────────
    def submit_for_review(
        self,
        *,
        plan: ModelingPlan,
        rendered_yaml: str,
        validation: ValidationReport,
        actor: str,
    ) -> ApprovalRecord:
        """Persist a DRAFT row. Always allowed."""
        record = make_record(
            plan_id=validation.plan_id,
            status=ApprovalStatus.DRAFT,
            actor=actor,
            plan_json=plan.model_dump_json(),
            validation_json=validation.model_dump_json(),
            previous_version=self._latest_version(validation.plan_id),
            rendered_yaml=rendered_yaml,
        )
        self._store.append(record)
        return record

    def approve(
        self,
        *,
        plan_id: str,
        actor: str,
        comment: str | None = None,
    ) -> ApprovalRecord:
        """Transition the latest DRAFT to APPROVED and persist YAML to the store."""
        latest = self._store.latest(plan_id)
        if latest is None:
            raise ApprovalGateError(f"No plan found for plan_id={plan_id}")
        if latest.validation_json:
            report = ValidationReport.model_validate_json(latest.validation_json)
            if not report.passed:
                raise ApprovalGateError(
                    f"Cannot approve plan_id={plan_id}: "
                    f"{report.summary.errors} ERROR-severity issues outstanding."
                )

        # Persist the approved YAML to the configured store (ADLS Gen2 or local).
        yaml_path: str | None = None
        if latest.rendered_yaml:
            catalog_id = catalog_from_yaml(latest.rendered_yaml)
            next_version = (latest.version or 0) + 1
            try:
                yaml_path = self._yaml_store.save(
                    catalog_id=catalog_id,
                    plan_id=plan_id,
                    version=next_version,
                    rendered_yaml=latest.rendered_yaml,
                )
            except Exception as exc:  # pragma: no cover
                # Storage failure must never block approval — log and continue.
                import logging

                logging.getLogger(__name__).error(
                    "Failed to persist YAML for plan_id=%s: %s", plan_id, exc
                )

            # Feedback loop: explode the approved plan into per-object rows and
            # append them to the learning corpus. Wrapped independently so a
            # corpus failure never blocks approval or the YAML store write.
            if self._example_store is not None and latest.plan_json:
                try:
                    plan = ModelingPlan.model_validate_json(latest.plan_json)
                    rows = plan_to_example_rows(
                        plan,
                        catalog_id=catalog_id,
                        plan_id=plan_id,
                        version=next_version,
                        approved_by=actor,
                    )
                    written = self._example_store.save_rows(rows)
                    import logging

                    logging.getLogger(__name__).info(
                        "Learning corpus: appended %d example(s) for plan_id=%s (v%d)",
                        written,
                        plan_id,
                        next_version,
                    )
                except Exception as exc:  # pragma: no cover
                    import logging

                    logging.getLogger(__name__).error(
                        "Failed to append learning examples for plan_id=%s: %s",
                        plan_id,
                        exc,
                    )

        record = make_record(
            plan_id=plan_id,
            status=ApprovalStatus.APPROVED,
            actor=actor,
            plan_json=latest.plan_json,
            validation_json=latest.validation_json,
            comment=comment,
            previous_version=latest.version,
            rendered_yaml=latest.rendered_yaml,
            yaml_path=yaml_path,
        )
        self._store.append(record)
        return record

    def reject(
        self,
        *,
        plan_id: str,
        actor: str,
        comment: str,
    ) -> ApprovalRecord:
        latest = self._store.latest(plan_id)
        if latest is None:
            raise ApprovalGateError(f"No plan found for plan_id={plan_id}")
        record = make_record(
            plan_id=plan_id,
            status=ApprovalStatus.REJECTED,
            actor=actor,
            plan_json=latest.plan_json,
            validation_json=latest.validation_json,
            comment=comment,
            previous_version=latest.version,
        )
        self._store.append(record)
        return record

    def request_changes(
        self,
        *,
        plan_id: str,
        actor: str,
        comment: str,
    ) -> ApprovalRecord:
        latest = self._store.latest(plan_id)
        if latest is None:
            raise ApprovalGateError(f"No plan found for plan_id={plan_id}")
        record = make_record(
            plan_id=plan_id,
            status=ApprovalStatus.CHANGES_REQUESTED,
            actor=actor,
            plan_json=latest.plan_json,
            validation_json=latest.validation_json,
            comment=comment,
            previous_version=latest.version,
        )
        self._store.append(record)
        return record

    def history(self, plan_id: str) -> tuple[ApprovalRecord, ...]:
        return self._store.history(plan_id)

    def list_recent(self, *, limit: int = 50) -> tuple[ApprovalRecord, ...]:
        return self._store.list_recent(limit=limit)

    # ── Pipeline orchestration (Phase B-2) ──────────────────────────────────
    def run_pipeline(
        self,
        pipeline_input: PipelineInput,
        *,
        run_id: str | None = None,
        acknowledge_risks: bool = False,
        stop_after: StopAfter | None = None,
    ) -> PipelineRun:
        """Run the full pipeline end-to-end and persist the result.

        Parameters
        ----------
        acknowledge_risks
            When True, supervisor-recommended pauses are surfaced on the run
            (so the UI keeps the banner) but execution continues to YAML.
        stop_after
            Internal checkpoint, used by tests; the public UI never sets it.
        """
        orchestrator = PipelineOrchestrator(
            schema_analyzer=self._schema_analyzer,
            bv_architect=self._bv_architect,
            yaml_generator=self._yaml_generator,
            supervisor=self._supervisor,
        )
        run = orchestrator.run(
            pipeline_input,
            stop_after=stop_after,
            run_id=run_id,
            acknowledge_risks=acknowledge_risks,
        )
        self._pipeline_run_store.save(run)
        return run

    def get_pipeline_run(self, run_id: str) -> PipelineRun | None:
        return self._pipeline_run_store.get(run_id)

    def list_pipeline_runs(self, *, limit: int = 50) -> tuple[PipelineRun, ...]:
        return self._pipeline_run_store.list_recent(limit=limit)

    # ── helpers ─────────────────────────────────────────────────────────────
    def _latest_version(self, plan_id: str) -> int | None:
        latest = self._store.latest(plan_id)
        return latest.version if latest else None

    @staticmethod
    def _now() -> datetime:
        # Centralised so tests can monkeypatch it.
        return datetime.now(timezone.utc)


# Convenience singleton for the API (override in tests via dependency_overrides).
_default_service: DwaService | None = None


def _try_build_default_schema_analyzer() -> SchemaAnalyzer | None:
    """Best-effort construction of a SchemaAnalyzer from environment settings.

    Returns ``None`` if Azure OpenAI configuration is missing/incomplete so the
    rest of the API stays usable (the analyze step will then surface
    ``LlmAgentNotConfiguredError`` only when actually invoked).
    """
    try:
        from dbt_builder.src.ai.agents.modeller import get_modelling_agent
        from dbt_builder.src.ai.agents.plan_reviewer import get_plan_reviewer

        agent = get_modelling_agent()
        reviewer = get_plan_reviewer()  # None unless plan review is enabled + configured
    except Exception:  # noqa: BLE001 — env not configured is an expected dev case
        return None

    if reviewer is None:
        # Single-model path (unchanged behaviour).
        return SchemaAnalyzer.from_modeller(agent)

    # Two-model path: the fast generator drafts the plan, the stronger reviewer
    # critiques and patches it before rendering. Review is fail-safe (returns the
    # original plan on any error), so this never weakens the single-model path.
    def _propose_and_review(payload: object) -> object:
        plan = agent.propose(payload)  # type: ignore[arg-type]
        return reviewer.review(plan, payload)  # type: ignore[arg-type]

    return SchemaAnalyzer(propose_fn=_propose_and_review)  # type: ignore[arg-type]


def _try_build_default_bv_architect() -> BvArchitect:
    """BvArchitect wired with the LLM BV-sat proposer when enabled.

    Falls back to a purely deterministic ``BvArchitect()`` (PITs + bridges only,
    no BV satellites) when the proposer is disabled or Azure OpenAI is not
    configured — so the default pipeline and all offline tests are unchanged.
    """
    try:
        from dbt_builder.src.ai.agents.bv_sat_proposer import get_bv_sat_proposer

        proposer = get_bv_sat_proposer()
    except Exception:  # noqa: BLE001 — env not configured is an expected dev case
        proposer = None
    if proposer is None:
        return BvArchitect()
    return BvArchitect(propose_bv_sats_fn=proposer.propose)


def get_service() -> DwaService:
    global _default_service
    if _default_service is None:
        _default_service = DwaService(
            schema_analyzer=_try_build_default_schema_analyzer(),
            bv_architect=_try_build_default_bv_architect(),
        )
    return _default_service


def set_service(service: DwaService | None) -> None:
    """Replace the singleton (used by tests)."""
    global _default_service
    _default_service = service


def _appease_unused_import(_: Any) -> None:  # pragma: no cover
    """Keep ``Any`` import — used by future typed kwargs."""
    return None


# Public facade surface: every name listed here is part of the contract the
# API / UI layers rely on. Keeping the list explicit also silences F401 for
# the deliberate re-exports above.
__all__ = [
    # Exceptions
    "ApprovalGateError",
    "LlmAgentNotConfiguredError",
    # Service
    "DwaService",
    "get_service",
    "set_service",
    # Contracts re-exported for caller convenience
    "ApprovalRecord",
    "ApprovalStatus",
    "BronzeSnapshot",
    "BvProposal",
    "CatalogSnapshot",
    "ChangeSet",
    "ModelingPlan",
    "PipelineRun",
    "PipelineRunStatus",
    "PipelineStepName",
    "PipelineStepResult",
    "RiskAssessment",
    "RiskKind",
    "RiskSeverity",
    "RiskSignal",
    "SourceSystem",
    "StopAfter",
    "SupervisionRecommendation",
    "ValidationReport",
    "YamlBundle",
    # Orchestration / supervision
    "PipelineInput",
    "PipelineOrchestrator",
    "PipelineSupervisor",
    "SupervisorConfig",
    # Stores
    "ApprovalStore",
    "InMemoryPipelineRunStore",
    "PipelineRunStore",
    "SqliteApprovalStore",
    "YamlStore",
    "LocalYamlStore",
    "get_pipeline_run_store",
    "set_pipeline_run_store",
    "make_record",
    "make_yaml_store",
    "catalog_from_yaml",
    # Agents (deterministic — safe to construct directly in tests)
    "BvArchitect",
    "SchemaAnalyzer",
    "YamlGenerator",
    # Validation helper
    "run_validation",
    # Pipeline submodules (used by the API for deterministic steps)
    "bronze_reader",
    "catalog_inspector",
    "diff_analyzer",
]
