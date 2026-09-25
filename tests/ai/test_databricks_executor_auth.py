"""Auth-selection tests for the shared Databricks executor builder.

These never open a connection — they assert which auth mechanism the executor
is wired with (PAT vs Azure AD credentials_provider) from settings alone.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from dbt_builder.src.ai.store.executor import (
    has_databricks_creds,
    make_databricks_executor,
)


def _settings(**overrides):
    base = dict(
        databricks_workspace_url="redacted-host.example.net",
        databricks_http_path="/sql/1.0/warehouses/abc",
        databricks_token=None,
        databricks_auth_type="pat",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_has_creds_false_without_host():
    assert has_databricks_creds(_settings(databricks_workspace_url=None)) is False


def test_has_creds_false_for_pat_without_token():
    assert has_databricks_creds(_settings(databricks_auth_type="pat")) is False


def test_has_creds_true_for_pat_with_token():
    assert has_databricks_creds(_settings(databricks_token="tok")) is True


def test_has_creds_true_for_azure_cli_without_token():
    # Entra auth needs no static token — the ambient az-login session is used.
    assert has_databricks_creds(_settings(databricks_auth_type="azure-cli")) is True


def test_make_executor_pat_uses_access_token():
    exe = make_databricks_executor(_settings(databricks_token="tok"))
    assert exe._access_token == "tok"
    assert exe._credentials_provider is None


def test_make_executor_azure_cli_uses_credentials_provider():
    exe = make_databricks_executor(_settings(databricks_auth_type="azure-cli"))
    # No static token; a lazy Entra credentials_provider is wired instead. The
    # provider closure defers the azure-identity import until first connect, so
    # constructing it here does not require azure or a live login.
    assert exe._access_token is None
    assert callable(exe._credentials_provider)


def test_make_executor_secretstr_token_unwrapped():
    class _Secret:
        def get_secret_value(self):
            return "unwrapped"

    exe = make_databricks_executor(_settings(databricks_token=_Secret()))
    assert exe._access_token == "unwrapped"


def test_make_executor_raises_without_creds():
    with pytest.raises(RuntimeError):
        make_databricks_executor(_settings(databricks_auth_type="pat"))
