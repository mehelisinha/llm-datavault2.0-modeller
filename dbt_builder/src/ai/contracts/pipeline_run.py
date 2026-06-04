"""Pipeline run contracts: state tracking for the multi-step orchestration.

These models form the shared language between:

* :class:`~dbt_builder.src.ai.orchestration.orchestrator.PipelineOrchestrator`
* :class:`~dbt_builder.src.ai.store.pipeline_run_store.InMemoryPipelineRunStore`
* The ``/api/pipeline`` FastAPI router

Keeping them in the contracts layer (a leaf in the import graph) means every
layer can import them without circular dependencies.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.bv import BvProposal
from dbt_builder.src.ai.contracts.catalog import BronzeSnapshot, CatalogSnapshot, ChangeSet
from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.contracts.payloads import SourceSystem
from dbt_builder.src.ai.contracts.supervision import RiskAssessment
from dbt_builder.src.ai.contracts.validation import ValidationReport


class StopAfter(str, Enum):
    """Internal pause checkpoints used by the orchestrator.

    Intentionally **not** exposed to end users — the public agentic surface
    is a single "Run pipeline" call. ``StopAfter`` lets the supervisor and
    automated tests stop a run at a deterministic point for inspection.
    """

    DIFF = "diff"
    PLAN = "plan"
    YAML = "yaml"


class PipelineRunStatus(str, Enum):
    """Coarse lifecycle state of a pipeline run."""

    RUNNING = "running"
    PAUSED = "paused"  # supervisor requested a human review checkpoint
    DONE = "done"  # all requested steps completed successfully
    FAILED = "failed"  # unrecoverable error; see error_detail


class PipelineStepName(str, Enum):
    """Stable identifiers for the five logical pipeline steps.

    Values appear in API responses and the UI progress timeline — renaming
    them is a breaking change because clients may store or compare them.
    """

    SNAPSHOT = "snapshot"  # Steps 1-3: inspect_catalog + read_bronze + diff
    ANALYZE = "analyze"  # Step 4:  SchemaAnalyzer (LLM)
    ARCHITECT_BV = "architect_bv"  # Step 4b: BvArchitect (deterministic)
    GENERATE = "generate"  # Step 5:  YamlGenerator (deterministic)
    DESCRIBE = "describe"  # Step 5b: Descriptor (LLM, descriptions only)
    VALIDATE = "validate"  # Step 6:  Validator (deterministic)


class PipelineStepResult(BaseModel):
    """Outcome record for a single pipeline step."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step: PipelineStepName
    status: Literal["ok", "failed"]
    duration_ms: int = Field(ge=0, description="Wall-clock time for this step in milliseconds.")
    error: str | None = Field(default=None, description="Error message when status is 'failed'.")


class PipelineRun(BaseModel):
    """Full state of a pipeline run, populated incrementally as steps complete.

    Artifact fields are ``None`` until the step that produces them finishes.
    ``status`` tracks the coarse lifecycle; ``steps`` records per-step timing
    and errors for the UI progress timeline.

    The model is intentionally **not** frozen: the store replaces the entire
    record on each save, and the orchestrator builds new instances via
    ``model_copy(update=…)`` at each step — so application-level immutability
    is maintained without Pydantic's frozen constraint.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    status: PipelineRunStatus
    stop_after: StopAfter | None = None
    steps: tuple[PipelineStepResult, ...] = ()

    # ── Artifacts (None until the producing step completes) ──────────────────
    system: SourceSystem | None = None
    catalog_snapshot: CatalogSnapshot | None = None
    bronze_snapshot: BronzeSnapshot | None = None
    change_set: ChangeSet | None = None
    plan: ModelingPlan | None = None
    bv: BvProposal | None = None
    validation: ValidationReport | None = None
    rendered_yaml: str | None = None

    # ── Error / risk state ───────────────────────────────────────────────────
    error_detail: str | None = None
    risk_assessment: RiskAssessment | None = None

    # ── Timestamps ───────────────────────────────────────────────────────────
    created_at: datetime
    updated_at: datetime
