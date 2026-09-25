"""Routes backing the History page (mockup 5).

Personal scope (default) returns only the caller's own approval transitions;
``scope=all`` returns the full audit trail and is gated to admins.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from dbt_builder.api.auth import UserIdentity, get_user_optional
from dbt_builder.api.settings import ApiSettings, get_settings
from dbt_builder.src.ai.contracts.approval import ApprovalRecord
from dbt_builder.src.ai.service import DwaService, get_service

router = APIRouter(prefix="/api/history", tags=["history"])

_PERSONAL_OVERSAMPLE = 10
_PERSONAL_HARD_CEILING = 500


def _filter_to_user(
    records: list[ApprovalRecord], email: str
) -> list[ApprovalRecord]:
    needle = email.lower()
    return [r for r in records if r.actor.lower() == needle]


@router.get("", response_model=list[ApprovalRecord])
def list_recent(
    limit: int = Query(default=50, ge=1, le=500),
    scope: Literal["mine", "all"] = Query(
        default="mine",
        description="'mine' returns the caller's own records; 'all' requires admin.",
    ),
    user: UserIdentity | None = Depends(get_user_optional),  # noqa: B008
    settings: ApiSettings = Depends(get_settings),  # noqa: B008
    service: DwaService = Depends(get_service),  # noqa: B008
) -> list[ApprovalRecord]:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view history.",
        )
    if scope == "all":
        if not user.is_admin(settings):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required to view all users' history.",
            )
        return list(service.list_recent(limit=limit))
    fetch_limit = min(limit * _PERSONAL_OVERSAMPLE, _PERSONAL_HARD_CEILING)
    raw = list(service.list_recent(limit=fetch_limit))
    return _filter_to_user(raw, user.email)[:limit]


@router.get("/{plan_id}", response_model=list[ApprovalRecord])
def history_for(
    plan_id: str,
    user: UserIdentity | None = Depends(get_user_optional),  # noqa: B008
    settings: ApiSettings = Depends(get_settings),  # noqa: B008
    service: DwaService = Depends(get_service),  # noqa: B008
) -> list[ApprovalRecord]:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view plan history.",
        )
    records = list(service.history(plan_id))
    if user.is_admin(settings):
        return records
    return _filter_to_user(records, user.email)
