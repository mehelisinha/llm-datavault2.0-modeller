"""Routes backing the Plan-builder pages.

Endpoints:

* ``POST /api/plans/validate``     — Step 6: Validator (always available).
* ``POST /api/plans/analyze``      — Step 4: SchemaAnalyzer (LLM; 503 if unwired).
* ``POST /api/plans/architect-bv`` — Step 4b: BV Architect (deterministic).
* ``POST /api/plans/generate``     — Step 5: YAML Generator (deterministic).

Every endpoint goes through :class:`DwaService` — never imports an
``ai/*`` internal directly. The architecture test enforces this so the
API surface stays small and the agents can refactor freely.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.bv import BvProposal
from dbt_builder.src.ai.contracts.catalog import BronzeSnapshot, ChangeSet
from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.contracts.payloads import SourceSystem
from dbt_builder.src.ai.contracts.validation import ValidationReport
from dbt_builder.src.ai.rendering.metadata_v3_emitter import render_v3
from dbt_builder.src.ai.service import (
    DwaService,
    LlmAgentNotConfiguredError,
    get_service,
)

router = APIRouter(prefix="/api/plans", tags=["plans"])

GenerateFormat = Literal["metadata_v3", "dbt_per_file"]


# ── Request bodies ──────────────────────────────────────────────────────────


class ValidateRequest(BaseModel):
    plan: ModelingPlan | None = None
    rendered_yaml: str | None = Field(default=None)
    # Business-vault proposal, so the dbt compile gate can materialise the full
    # model set. The gate's project path / enablement come from server settings
    # (not the request) so clients can't redirect the build target.
    bv: BvProposal | None = None


class AnalyzeRequest(BaseModel):
    """Inputs for Step 4 — Schema Analyzer.

    ``system`` and ``bronze`` are produced by the discovery + bronze-reader
    steps; ``change_set`` is the diff analyzer's output. The UI fetches
    them via earlier endpoints and re-posts them here so the call is
    explicit and the API stays stateless.
    """

    model_config = ConfigDict(extra="forbid")

    system: SourceSystem
    bronze: BronzeSnapshot
    change_set: ChangeSet


class GenerateRequest(BaseModel):
    """Inputs for Step 5 — YAML Generator.

    The default ``format`` (``metadata_v3``) renders a single monolithic
    document and requires ``system`` so the ``system:`` block can be filled
    in. ``dbt_per_file`` keeps the legacy per-object output and ignores
    ``system``.
    """

    model_config = ConfigDict(extra="forbid")

    plan: ModelingPlan
    bv: BvProposal | None = None
    system: SourceSystem | None = None
    format: GenerateFormat = "metadata_v3"


# ── Response bodies ─────────────────────────────────────────────────────────


class GeneratedYamlFile(BaseModel):
    """API-friendly view of a YamlFile (text body, not bytes)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    body: str = Field(description="UTF-8 decoded YAML content.")


class GenerateResponse(BaseModel):
    """Step 5 output. Exactly one of ``monolithic_yaml`` or ``files`` is set.

    ``metadata_v3`` returns a single document in ``monolithic_yaml``;
    ``dbt_per_file`` returns one file per object in ``files``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    files: tuple[GeneratedYamlFile, ...] = ()
    monolithic_yaml: str | None = None


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/validate", response_model=ValidationReport)
def validate(
    body: ValidateRequest,
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> ValidationReport:
    if body.plan is None and body.rendered_yaml is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of 'plan' or 'rendered_yaml' must be supplied.",
        )
    return service.validate(
        plan=body.plan,
        rendered_yaml=body.rendered_yaml,
        bv=body.bv,
    )


@router.post("/analyze", response_model=ModelingPlan)
def analyze(
    body: AnalyzeRequest,
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> ModelingPlan:
    """Step 4 — SchemaAnalyzer LLM agent."""
    try:
        return service.analyze(
            system=body.system,
            bronze=body.bronze,
            change_set=body.change_set,
        )
    except LlmAgentNotConfiguredError as exc:
        # 503: the route exists but the LLM dependency is not wired in this
        # deployment. Distinct from 501 (not implemented) and 500 (bug).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/architect-bv", response_model=BvProposal)
def architect_bv(
    plan: ModelingPlan,
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> BvProposal:
    """Step 4b — BV Architect (deterministic)."""
    return service.architect_bv(plan)


@router.post("/generate", response_model=GenerateResponse)
def generate(
    body: GenerateRequest,
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> GenerateResponse:
    """Step 5 — YAML Generator (deterministic).

    ``metadata_v3`` (default): single monolithic document via ``render_v3``;
    ``files`` is empty.
    ``dbt_per_file``: legacy per-object output via ``service.generate_yaml``;
    ``monolithic_yaml`` is ``None``.
    """
    if body.format == "metadata_v3":
        if body.system is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'system' is required when format='metadata_v3'.",
            )
        yaml_text = render_v3(plan=body.plan, system=body.system, bv=body.bv)
        return GenerateResponse(monolithic_yaml=yaml_text)

    bundle = service.generate_yaml(plan=body.plan, bv=body.bv)
    return GenerateResponse(
        files=tuple(
            GeneratedYamlFile(path=f.path, body=f.body.decode("utf-8")) for f in bundle.files
        ),
    )
