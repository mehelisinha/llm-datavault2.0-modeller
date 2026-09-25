"""Tests for /api/pipeline/run discovery-mode wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dbt_builder.api import create_app
from dbt_builder.api.settings import ApiSettings, get_settings
from dbt_builder.src.ai.service import set_service


def _col(name: str, dtype: str = "string") -> MagicMock:
    c = MagicMock()
    c.name = name
    c.type_text = dtype
    c.nullable = True
    c.comment = None
    c.partition_index = None
    return c


def _table(name: str, *, table_type: str = "TABLE") -> MagicMock:
    t = MagicMock()
    t.name = name
    t.table_type = table_type
    return t


class _FakeTables:
    def __init__(self, by_schema: dict[str, list[MagicMock]]) -> None:
        self._by_schema = by_schema

    def list(self, *, catalog_name: str, schema_name: str) -> list[MagicMock]:
        return list(self._by_schema.get(schema_name, []))

    def get(self, *, full_name: str) -> MagicMock:
        _catalog, schema, table = full_name.split(".", 2)
        info = MagicMock()
        info.columns = [_col("mrid"), _col("name")]
        return info


@pytest.fixture()
def databricks_pipeline_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """API client with discovery_mode=databricks and a mocked WorkspaceClient."""
    fake_tables = _FakeTables(
        {
            "eam": [_table("asset"), _table("equipment")],
            "raw_vault": [_table("hub_asset", table_type="TABLE")],
        }
    )
    fake_client = MagicMock()
    fake_client.tables = fake_tables

    monkeypatch.setattr(
        "dbt_builder.api.databricks_uc.get_workspace_client",
        lambda _settings: fake_client,
    )

    settings = ApiSettings(
        discovery_mode="databricks",
        databricks_host="https://adb-example.azuredatabricks.net",
        databricks_auth_type="azure-cli",
        default_system_id="test_sys",
        default_system_name="Test System",
        default_record_source="test_sys",
    )
    # SchemaAnalyzer / ModellingAgent are not configured in unit tests — the run
    # will fail at ANALYZE unless we stub the service. We only assert SNAPSHOT here.
    get_settings.cache_clear()
    set_service(None)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield TestClient(app)
    finally:
        set_service(None)
        get_settings.cache_clear()


def test_pipeline_run_uses_databricks_callables_for_bronze(
    databricks_pipeline_client: TestClient,
) -> None:
    """Pipeline must not use stub YAML when discovery_mode=databricks.

    Regression: UI listed live UC tables but /api/pipeline/run always called
    make_stub_callables_for_catalog, yielding an empty bronze snapshot.
    """
    r = databricks_pipeline_client.post(
        "/api/pipeline/run",
        json={
            "catalog": "edh_unreg_bronze_dev",
            "bronze_schema": "eam",
            "vault_schema": "raw_vault",
            "system_id": "eam",
            "system_name": "EAM",
            "source_type": "delta",
            "tables": ["asset"],
        },
    )
    # Run is created even when a later step fails (orchestrator records step errors).
    assert r.status_code == 201, r.text
    data = r.json()
    bronze = data.get("bronze_snapshot")
    assert bronze is not None
    assert bronze["schema_name"] == "eam"
    assert len(bronze["tables"]) == 1
    assert bronze["tables"][0]["name"] == "asset"


def test_pipeline_run_greenfield_omits_vault_schema(
    databricks_pipeline_client: TestClient,
) -> None:
    r = databricks_pipeline_client.post(
        "/api/pipeline/run",
        json={
            "catalog": "edh_unreg_bronze_dev",
            "bronze_schema": "eam",
            "system_id": "eam",
            "system_name": "EAM",
            "source_type": "delta",
            "tables": ["asset"],
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["catalog_snapshot"]["entities"] == []
    assert data["change_set"]["changes"][0]["category"] == "new"
