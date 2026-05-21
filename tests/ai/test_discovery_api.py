"""Discovery API — stub mode."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dbt_builder.api import create_app
from dbt_builder.api.settings import get_settings
from dbt_builder.src.ai.service import set_service


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("DWA_API_DISCOVERY_MODE", "stub")
    get_settings.cache_clear()
    set_service(None)
    try:
        yield TestClient(create_app())
    finally:
        set_service(None)
        get_settings.cache_clear()


def test_list_catalogs(client: TestClient) -> None:
    r = client.get("/api/discovery/catalogs")
    assert r.status_code == 200, r.text
    catalogs = r.json()["catalogs"]
    assert "edh_unreg_silver_dev_st" in catalogs


def test_list_schemas(client: TestClient) -> None:
    r = client.get("/api/discovery/catalogs/edh_unreg_silver_dev_st/schemas")
    assert r.status_code == 200, r.text
    schemas = r.json()["schemas"]
    assert "bronze" in schemas
    assert "raw_vault" in schemas


def test_snapshot_returns_pipeline_artifacts(client: TestClient) -> None:
    r = client.post(
        "/api/discovery/snapshot",
        json={
            "catalog": "edh_unreg_silver_dev_st",
            "bronze_schema": "bronze",
            "vault_schema": "raw_vault",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["system"]["catalog"] == "edh_unreg_silver_dev_st"
    assert len(data["change_set"]["changes"]) > 0
