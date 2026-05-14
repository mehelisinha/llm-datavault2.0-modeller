"""Routes backing the Review page.

Phase A exposes the validator endpoint so the UI can render the green/red
"Validation passed / N issues" banner. The analyze (Step 4) and generate
(Step 5) endpoints are placeholders that 501 until Phase B connects the
Schema Analyzer + YAML Generator agents.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.contracts.validation import ValidationReport
from dbt_builder.src.ai.service import DwaService, get_service

router = APIRouter(prefix="/api/plans", tags=["plans"])


class ValidateRequest(BaseModel):
    plan: ModelingPlan | None = None
    rendered_yaml: str | None = Field(default=None)
    dbt_project_path: str | None = None


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
        dbt_project_path=body.dbt_project_path,
    )


@router.post("/analyze", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def analyze() -> dict[str, str]:
    """Step 4 — Schema Analyzer LLM agent. Wired in Phase B."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Schema Analyzer agent is wired in Phase B.",
    )


@router.post("/generate", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def generate() -> dict[str, str]:
    """Step 5 — YAML Generator LLM agent. Wired in Phase B."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="YAML Generator agent is wired in Phase B.",
    )
