"""Reviewer identity: Entra JWT (production) or X-Actor header (development)."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from dbt_builder.api.settings import ApiSettings, get_settings

_jwk_clients: dict[str, PyJWKClient] = {}


def _jwks_client(settings: ApiSettings) -> PyJWKClient:
    uri = settings.aad_jwks_uri
    if uri is None:
        raise RuntimeError("JWKS URI is not configured")
    if uri not in _jwk_clients:
        _jwk_clients[uri] = PyJWKClient(uri)
    return _jwk_clients[uri]


def _actor_from_bearer(token: str, settings: ApiSettings) -> str:
    try:
        signing_key = _jwks_client(settings).get_signing_key_from_jwt(token)
        claims = jwt.decode(
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

    for key in ("preferred_username", "upn", "email", "sub"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token is valid but carries no usable identity claim.",
    )


def get_actor(
    authorization: Annotated[str | None, Header()] = None,
    x_actor: Annotated[str | None, Header(alias="X-Actor")] = None,
    settings: ApiSettings = Depends(get_settings),  # noqa: B008
) -> str:
    """Resolve the reviewer identity for mutating endpoints."""
    if settings.auth_enabled:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization: Bearer <token> required when Entra auth is enabled.",
            )
        return _actor_from_bearer(authorization.split(" ", 1)[1].strip(), settings)

    if x_actor and x_actor.strip():
        return x_actor.strip()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing X-Actor header (development mode).",
    )


def get_actor_optional(
    authorization: Annotated[str | None, Header()] = None,
    x_actor: Annotated[str | None, Header(alias="X-Actor")] = None,
    settings: ApiSettings = Depends(get_settings),  # noqa: B008
) -> str | None:
    """Best-effort actor for read-only routes (history, discovery)."""
    if settings.auth_enabled:
        if authorization and authorization.lower().startswith("bearer "):
            return _actor_from_bearer(authorization.split(" ", 1)[1].strip(), settings)
        return None
    return x_actor.strip() if x_actor and x_actor.strip() else None
