"""`/api/me` — caller identity used by the UI to render the header & nav.

The UI calls this once after login to decide which user-info to show, whether
to expose the admin 'All users' toggle on the history page, and whether
authentication is even configured server-side.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from dbt_builder.api.auth import UserIdentity, get_user_optional
from dbt_builder.api.settings import ApiSettings, get_settings

router = APIRouter(prefix="/api/me", tags=["meta"])


class MeResponse(BaseModel):
    """Minimum identity payload required by the UI shell."""

    model_config = ConfigDict(extra="forbid")

    authenticated: bool
    auth_enabled: bool
    email: str | None = None
    roles: list[str] = []
    is_admin: bool = False


@router.get("", response_model=MeResponse)
def me(
    user: UserIdentity | None = Depends(get_user_optional),  # noqa: B008
    settings: ApiSettings = Depends(get_settings),  # noqa: B008
) -> MeResponse:
    if user is None:
        return MeResponse(authenticated=False, auth_enabled=settings.auth_enabled)
    return MeResponse(
        authenticated=True,
        auth_enabled=settings.auth_enabled,
        email=user.email,
        roles=sorted(user.roles),
        is_admin=user.is_admin(settings),
    )
