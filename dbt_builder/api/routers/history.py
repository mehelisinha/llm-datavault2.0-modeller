"""Routes backing the History page (mockup 5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from dbt_builder.src.ai.contracts.approval import ApprovalRecord
from dbt_builder.src.ai.service import DwaService, get_service

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[ApprovalRecord])
def list_recent(
    limit: int = Query(default=50, ge=1, le=500),
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> list[ApprovalRecord]:
    return list(service.list_recent(limit=limit))


@router.get("/{plan_id}", response_model=list[ApprovalRecord])
def history_for(
    plan_id: str,
    service: DwaService = Depends(get_service),  # noqa: B008  FastAPI dependency
) -> list[ApprovalRecord]:
    return list(service.history(plan_id))
