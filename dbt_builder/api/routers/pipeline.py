"""Pipeline-run endpoints.

The agentic surface for the UI: one POST to run the whole pipeline, one GET
to poll its progress.  Internally the orchestrator handles step sequencing,
risk supervision, and YAML generation; the UI only sees the high-level run
artifact.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.api.discovery_callables import (
    resolve_snapshot_callables,
    tables_to_include_patterns,
)
from dbt_builder.api.settings import ApiSettings, get_settings
from dbt_builder.src.ai.contracts.payloads import SourceSystem
from dbt_builder.src.ai.contracts.pipeline_run import PipelineRun
from dbt_builder.src.ai.service import (
    DwaService,
    PipelineInput,
    get_service,
)

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


# ── Request body ────────────────────────────────────────────────────────────


class PipelineRunRequest(BaseModel):
    """User-facing request to run the full pipeline.

    Deliberately omits ``stop_after``: the public flow is always "all the way
    to YAML, paused only when the supervisor flags risk".  Acknowledging the
    risk is the only knob exposed to the operator.
    """

    model_config = ConfigDict(extra="forbid")

    catalog: str = Field(..., min_length=1)
    bronze_schema: str = Field(..., min_length=1)
    # Optional: omit for greenfield builds (diff treats every bronze table as NEW).
    vault_schema: str | None = Field(default=None, min_length=1)
    system_id: str = Field(..., min_length=1)
    system_name: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)
    record_source: str | None = None

    # Explicit table allowlist (same semantics as /api/discovery/snapshot).
    tables: tuple[str, ...] = ()
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()

    acknowledge_risks: bool = False


# ── Catalog adapter ─────────────────────────────────────────────────────────


def _build_pipeline_input(req: PipelineRunRequest, settings: ApiSettings) -> PipelineInput:
    """Translate the request into a :class:`PipelineInput`.

    Catalog callables are resolved from ``settings.discovery_mode`` so the
    pipeline reads the same source as the discovery dropdowns (stub YAML,
    Unity Catalog REST, or Spark).
    """
    (
        list_vault_entities,
        describe_vault,
        list_bronze_tables,
        describe_bronze,
    ) = resolve_snapshot_callables(
        settings,
        catalog=req.catalog,
        bronze_schema=req.bronze_schema,
        vault_schema=req.vault_schema,
    )

    system = SourceSystem(
        system_id=req.system_id,
        system_name=req.system_name,
        source_type=req.source_type,
        record_source=req.record_source or req.system_id,
    )
    return PipelineInput(
        catalog=req.catalog,
        bronze_schema=req.bronze_schema,
        vault_schema=req.vault_schema,
        system=system,
        list_vault_entities=list_vault_entities,
        describe_vault=describe_vault,
        list_bronze_tables=list_bronze_tables,
        describe_bronze=describe_bronze,
        include_patterns=tables_to_include_patterns(req.tables, req.include_patterns),
        exclude_patterns=req.exclude_patterns,
    )


# ── Routes ──────────────────────────────────────────────────────────────────


@router.post("/run", response_model=PipelineRun, status_code=status.HTTP_201_CREATED)
def run_pipeline(
    req: PipelineRunRequest,
    settings: Annotated[ApiSettings, Depends(get_settings)],
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> PipelineRun:
    """Execute the pipeline end-to-end and return the run artifact.

    The run is persisted in the in-memory pipeline-run store; the UI re-fetches
    it via :func:`get_pipeline_run` to drive the live timeline.
    """
    pipeline_input = _build_pipeline_input(req, settings)
    _LOG.info(
        "POST /api/pipeline/run start: catalog=%s bronze_schema=%s tables=%d ack_risks=%s",
        req.catalog,
        req.bronze_schema,
        len(req.tables),
        req.acknowledge_risks,
    )
    t0 = time.perf_counter()
    try:
        run = service.run_pipeline(
            pipeline_input,
            acknowledge_risks=req.acknowledge_risks,
        )
    except Exception as exc:  # noqa: BLE001 — surface internals as 500 with detail
        _LOG.exception(
            "Pipeline run failed before reaching the orchestrator after %.1fs",
            time.perf_counter() - t0,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    _LOG.info(
        "POST /api/pipeline/run done in %.1fs: run_id=%s status=%s",
        time.perf_counter() - t0,
        run.run_id,
        getattr(run, "status", "?"),
    )
    return run


@router.get("/runs/{run_id}", response_model=PipelineRun)
def get_pipeline_run(
    run_id: str,
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> PipelineRun:
    run = service.get_pipeline_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline run {run_id!r} not found.",
        )
    return run


@router.get("/runs", response_model=list[PipelineRun])
def list_pipeline_runs(
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
    limit: int = 50,
) -> list[PipelineRun]:
    return list(service.list_pipeline_runs(limit=limit))
