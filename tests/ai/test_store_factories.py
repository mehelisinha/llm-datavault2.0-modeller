"""Factory dispatch tests for make_yaml_store + make_approval_store + make_gitlab_publisher.

These don't reach Databricks or GitLab — they assert the returned class
type based on settings, using minimal AISettings stubs so the test
suite stays hermetic.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from dbt_builder.src.ai.integrations.gitlab import make_gitlab_publisher
from dbt_builder.src.ai.store.approval_store import make_approval_store
from dbt_builder.src.ai.store.yaml_store import make_yaml_store
from dbt_builder.src.utils.gitlab_mr import GitLabMrPublisher


def _settings(**overrides):
    base = dict(
        metadata_store_backend="auto",
        metadata_store_account=None,
        metadata_store_container="c",
        metadata_store_sp_client_id=None,
        metadata_store_sp_client_secret=None,
        metadata_store_tenant_id=None,
        databricks_workspace_url=None,
        databricks_http_path=None,
        databricks_token=None,
        metadata_delta_catalog="dwa_meta",
        metadata_delta_schema="default",
        metadata_delta_yaml_table="yaml_versions",
        metadata_delta_approvals_table="approvals",
        gitlab_base_url=None,
        gitlab_token=None,
        gitlab_project_id=None,
        gitlab_default_branch="approved-yaml",
        gitlab_storage_root_branch="main",
        gitlab_yaml_path_template="catalogs/{catalog}/latest.yaml",
        gitlab_branch_template="dwa/approve/{catalog}/{plan_id}-v{version}",
        gitlab_mr_title_template="[DWA] {catalog} v{version}",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_make_yaml_store_defaults_to_local():
    from dbt_builder.src.utils.yaml_store import LocalYamlStore

    store = make_yaml_store(_settings())
    assert isinstance(store, LocalYamlStore)


def test_make_yaml_store_explicit_delta_without_creds_raises():
    with pytest.raises(RuntimeError):
        make_yaml_store(_settings(metadata_store_backend="delta"))


def test_make_yaml_store_rejects_unknown_backend():
    with pytest.raises(ValueError):
        make_yaml_store(_settings(metadata_store_backend="ftp"))


def test_make_approval_store_defaults_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from dbt_builder.src.ai.store import SqliteApprovalStore

    store = make_approval_store(_settings())
    assert isinstance(store, SqliteApprovalStore)


def test_make_approval_store_explicit_delta_without_creds_raises():
    with pytest.raises(RuntimeError):
        make_approval_store(_settings(metadata_store_backend="delta"))


def test_make_gitlab_publisher_disabled_when_unconfigured():
    assert make_gitlab_publisher(_settings()) is None


def test_make_gitlab_publisher_returns_publisher_when_configured():
    pub = make_gitlab_publisher(
        _settings(
            gitlab_base_url="https://git.example.com",
            gitlab_token="t",
            gitlab_project_id="42",
        )
    )
    assert isinstance(pub, GitLabMrPublisher)
