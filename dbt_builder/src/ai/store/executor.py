"""Shared builder: :class:`AISettings` → :class:`DatabricksSqlExecutor`.

Both ``make_yaml_store`` and ``make_approval_store`` need an executor built the
same way (same host / http_path / auth). Centralising it here keeps the
PAT-vs-Entra auth decision — and the "are creds present?" check — in ONE place
instead of duplicated across the two factories.

Auth selection is driven by ``AISettings.databricks_auth_type``:

* ``"pat"`` (default) — static Personal Access Token (``databricks_token``).
* Any value in :data:`~dbt_builder.src.utils.databricks_sql.AAD_AUTH_TYPES`
  (e.g. ``"azure-cli"``) — Azure AD (Entra) via the ambient login session; no
  static token required. Use this when the workspace disables PATs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbt_builder.src.utils.databricks_sql import (
    AAD_AUTH_TYPES,
    DatabricksSqlExecutor,
    azure_ad_credentials_provider,
)

if TYPE_CHECKING:
    from dbt_builder.src.ai.settings import AISettings


def _auth_type(settings: AISettings) -> str:
    return (getattr(settings, "databricks_auth_type", "pat") or "pat").lower()


def has_databricks_creds(settings: AISettings) -> bool:
    """True when settings carry enough to open a Databricks SQL connection.

    Host + HTTP path are always required. A static PAT is required only for
    ``pat`` auth; Azure AD auth types authenticate via the ambient az-login /
    managed-identity session, so no token needs to be present.
    """
    if not (
        getattr(settings, "databricks_workspace_url", None)
        and getattr(settings, "databricks_http_path", None)
    ):
        return False
    if _auth_type(settings) in AAD_AUTH_TYPES:
        return True
    return bool(getattr(settings, "databricks_token", None))


def make_databricks_executor(settings: AISettings) -> DatabricksSqlExecutor:
    """Build a :class:`DatabricksSqlExecutor` from settings, honouring auth type.

    Raises ``RuntimeError`` if the settings do not carry enough to authenticate
    (mirrors :func:`has_databricks_creds`), so callers get a clear message rather
    than a connector-level failure.
    """
    if not has_databricks_creds(settings):
        raise RuntimeError(
            "Databricks connection requires databricks_workspace_url, "
            "databricks_http_path and either a databricks_token (pat auth) or "
            "databricks_auth_type set to an Azure AD type (e.g. azure-cli)."
        )
    host = str(settings.databricks_workspace_url)
    http_path = str(settings.databricks_http_path)
    auth_type = _auth_type(settings)

    if auth_type in AAD_AUTH_TYPES:
        return DatabricksSqlExecutor(
            server_hostname=host,
            http_path=http_path,
            credentials_provider=azure_ad_credentials_provider(auth_type=auth_type),
        )

    token = settings.databricks_token
    token_value = token.get_secret_value() if hasattr(token, "get_secret_value") else str(token)
    return DatabricksSqlExecutor(
        server_hostname=host, http_path=http_path, access_token=token_value
    )


__all__ = ["has_databricks_creds", "make_databricks_executor"]
