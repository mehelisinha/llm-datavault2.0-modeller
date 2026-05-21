"""Routes backing the Submit / Approve / Reject / Request changes buttons."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.approval import ApprovalRecord
from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.contracts.validation import ValidationReport
from dbt_builder.src.ai.service import ApprovalGateError, DwaService, get_service

router = APIRouter(prefix="/api/plans", tags=["approvals"])


class CommentBody(BaseModel):
    comment: str | None = Field(default=None, max_length=4000)


class RejectBody(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)


class SubmitForReviewRequest(BaseModel):
    """Inputs to create a DRAFT approval row.

    The URL path carries the canonical ``plan_id`` and must match
    ``validation.plan_id`` — otherwise the caller is confused about
    which plan it is submitting and we 422 rather than silently using
    the body's plan_id.
    """

    model_config = ConfigDict(extra="forbid")

    plan: ModelingPlan
    rendered_yaml: str = Field(min_length=1)
    validation: ValidationReport


def _require_actor(x_actor: str | None = Header(default=None)) -> str:
    if not x_actor:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Actor header. (Phase A: Entra integration pending.)",
        )
    return x_actor


@router.post("/{plan_id}/submit-for-review", response_model=ApprovalRecord)
def submit_for_review(
    plan_id: str,
    body: SubmitForReviewRequest,
    actor: str = Depends(_require_actor),  # noqa: B008  FastAPI dependency
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> ApprovalRecord:
    """Persist the current plan as a DRAFT, unlocking the approval buttons."""
    if plan_id != body.validation.plan_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Path plan_id '{plan_id}' does not match "
                f"validation.plan_id '{body.validation.plan_id}'."
            ),
        )
    return service.submit_for_review(
        plan=body.plan,
        rendered_yaml=body.rendered_yaml,
        validation=body.validation,
        actor=actor,
    )


@router.post("/{plan_id}/approve", response_model=ApprovalRecord)
def approve(
    plan_id: str,
    body: CommentBody,
    actor: str = Depends(_require_actor),  # noqa: B008  FastAPI dependency
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> ApprovalRecord:
    try:
        return service.approve(plan_id=plan_id, actor=actor, comment=body.comment)
    except ApprovalGateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{plan_id}/reject", response_model=ApprovalRecord)
def reject(
    plan_id: str,
    body: RejectBody,
    actor: str = Depends(_require_actor),  # noqa: B008  FastAPI dependency
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> ApprovalRecord:
    try:
        return service.reject(plan_id=plan_id, actor=actor, comment=body.comment)
    except ApprovalGateError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{plan_id}/request-changes", response_model=ApprovalRecord)
def request_changes(
    plan_id: str,
    body: RejectBody,
    actor: str = Depends(_require_actor),  # noqa: B008  FastAPI dependency
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> ApprovalRecord:
    try:
        return service.request_changes(plan_id=plan_id, actor=actor, comment=body.comment)
    except ApprovalGateError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
