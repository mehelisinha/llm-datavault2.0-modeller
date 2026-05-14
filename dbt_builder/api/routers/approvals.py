"""Routes backing the Approve / Request changes / Reject buttons."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from dbt_builder.src.ai.contracts.approval import ApprovalRecord
from dbt_builder.src.ai.service import ApprovalGateError, DwaService, get_service

router = APIRouter(prefix="/api/plans", tags=["approvals"])


class CommentBody(BaseModel):
    comment: str | None = Field(default=None, max_length=4000)


class RejectBody(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)


def _require_actor(x_actor: str | None = Header(default=None)) -> str:
    if not x_actor:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Actor header. (Phase A: Entra integration pending.)",
        )
    return x_actor


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
