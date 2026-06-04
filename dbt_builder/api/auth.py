"""Reviewer identity resolution.

Three concerns live here, kept in one module so wiring is DRY:

* Parsing the bearer token (when Entra is configured) or falling back to the
  ``X-Actor`` header (dev mode).
* Modelling the resolved identity (``UserIdentity``) with email + roles, and
  deriving ``is_admin`` from either the ``roles`` claim or the env-driven
  ``admin_emails`` allowlist.
* Exposing FastAPI dependencies (``get_user``, ``get_user_optional``,
  ``require_admin``) and the back-compat string-returning helpers
  (``get_actor``, ``get_actor_optional``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from dbt_builder.api.settings import ApiSettings, get_settings

_jwk_clients: dict[str, PyJWKClient] = {}


# ── Identity model ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class UserIdentity:
    """Resolved caller identity.

    ``email`` is the canonical actor string persisted in approval records.
    ``roles`` mirrors the Entra ``roles`` claim (app roles) and is empty in
    dev mode. ``is_admin`` is derived against the configured admin app-role
    OR the env-driven email allowlist so admins can be granted access before
    app-role assignments are completed.
    """

    email: str
    roles: frozenset[str] = field(default_factory=frozenset)

    def is_admin(self, settings: ApiSettings) -> bool:
        admin_role = settings.aad_admin_app_role.strip().lower()
        if admin_role and any(r.lower() == admin_role for r in self.roles):
            return True
        return self.email.lower() in settings.admin_email_set


# ── Token / header parsing ───────────────────────────────────────────────────


def _jwks_client(settings: ApiSettings) -> PyJWKClient:
    uri = settings.aad_jwks_uri
    if uri is None:
        raise RuntimeError("JWKS URI is not configured")
    if uri not in _jwk_clients:
        _jwk_clients[uri] = PyJWKClient(uri)
    return _jwk_clients[uri]


def _claims_from_bearer(token: str, settings: ApiSettings) -> dict[str, Any]:
    try:
        signing_key = _jwks_client(settings).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.aad_api_client_id,
            issuer=settings.aad_issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid bearer token: {exc}",
        ) from exc


def _identity_from_claims(claims: dict[str, Any]) -> UserIdentity:
    for key in ("preferred_username", "upn", "email", "sub"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            email = value.strip()
            break
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is valid but carries no usable identity claim.",
        )
    raw_roles = claims.get("roles") or []
    roles = frozenset(r for r in raw_roles if isinstance(r, str) and r.strip())
    return UserIdentity(email=email, roles=roles)


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return None
    return parts[1].strip()


# ── FastAPI dependencies ─────────────────────────────────────────────────────


def get_user(
    authorization: Annotated[str | None, Header()] = None,
    x_actor: Annotated[str | None, Header(alias="X-Actor")] = None,
    settings: ApiSettings = Depends(get_settings),  # noqa: B008
) -> UserIdentity:
    """Resolve the caller identity for mutating endpoints (401 on failure)."""
    if settings.auth_enabled:
        token = _bearer_token(authorization)
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization: Bearer <token> required when Entra auth is enabled.",
            )
        return _identity_from_claims(_claims_from_bearer(token, settings))

    if x_actor and x_actor.strip():
        return UserIdentity(email=x_actor.strip())
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing X-Actor header (development mode).",
    )


def get_user_optional(
    authorization: Annotated[str | None, Header()] = None,
    x_actor: Annotated[str | None, Header(alias="X-Actor")] = None,
    settings: ApiSettings = Depends(get_settings),  # noqa: B008
) -> UserIdentity | None:
    """Best-effort identity for read-only routes (returns None instead of 401)."""
    if settings.auth_enabled:
        token = _bearer_token(authorization)
        if token is None:
            return None
        return _identity_from_claims(_claims_from_bearer(token, settings))
    if x_actor and x_actor.strip():
        return UserIdentity(email=x_actor.strip())
    return None


def require_admin(
    user: UserIdentity = Depends(get_user),  # noqa: B008
    settings: ApiSettings = Depends(get_settings),  # noqa: B008
) -> UserIdentity:
    """Require the caller to be an admin, otherwise 403."""
    if not user.is_admin(settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for this operation.",
        )
    return user


# ── Back-compat string helpers (existing callers) ────────────────────────────


def get_actor(user: UserIdentity = Depends(get_user)) -> str:  # noqa: B008
    return user.email


def get_actor_optional(
    user: UserIdentity | None = Depends(get_user_optional),  # noqa: B008
) -> str | None:
    return user.email if user else None
