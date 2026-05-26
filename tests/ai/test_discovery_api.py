"""Discovery API — stub mode + databricks (Unity Catalog REST) mode."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dbt_builder.api import create_app, databricks_uc
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


# ---------------------------------------------------------------------------
# Databricks (Unity Catalog REST) mode — fully mocked, no live calls
# ---------------------------------------------------------------------------


def _col(
    name: str,
    type_text: str = "string",
    nullable: bool = True,
    comment: str | None = None,
    partition_index: int | None = None,
) -> SimpleNamespace:
    """Build a fake ``ColumnInfo``-shaped object the adapter knows how to read."""
    return SimpleNamespace(
        name=name,
        type_text=type_text,
        nullable=nullable,
        comment=comment,
        partition_index=partition_index,
    )


def _table(
    name: str,
    table_type: str = "MANAGED",
    columns: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    """Build a fake ``TableInfo``-shaped object."""
    return SimpleNamespace(
        name=name,
        table_type=SimpleNamespace(value=table_type),
        columns=columns or [],
    )


class _FakeCatalogs:
    def __init__(self, names: list[str]) -> None:
        self._names = names

    def list(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name=n) for n in self._names]


class _FakeSchemas:
    def __init__(self, by_catalog: dict[str, list[str]]) -> None:
        self._by_catalog = by_catalog

    def list(self, catalog_name: str) -> list[SimpleNamespace]:
        return [SimpleNamespace(name=n) for n in self._by_catalog.get(catalog_name, [])]


class _FakeTables:
    """Returns lists from ``.list(...)`` and full descriptions from ``.get(...)``."""

    def __init__(
        self,
        by_schema: dict[tuple[str, str], list[SimpleNamespace]],
        descriptions: dict[str, list[SimpleNamespace]] | None = None,
    ) -> None:
        self._by_schema = by_schema
        self._descriptions = descriptions or {}

    def list(self, catalog_name: str, schema_name: str) -> list[SimpleNamespace]:
        return list(self._by_schema.get((catalog_name, schema_name), []))

    def get(self, full_name: str) -> SimpleNamespace:
        if full_name in self._descriptions:
            cols = self._descriptions[full_name]
            return SimpleNamespace(name=full_name.split(".")[-1], columns=cols)
        # Fallback to the same TableInfo as listed (columns may be empty).
        for tables in self._by_schema.values():
            for t in tables:
                if full_name.endswith(f".{t.name}"):
                    return t
        raise KeyError(full_name)


class _FakeWorkspaceClient:
    def __init__(
        self,
        catalogs: list[str],
        schemas: dict[str, list[str]],
        tables: dict[tuple[str, str], list[SimpleNamespace]],
        table_descriptions: dict[str, list[SimpleNamespace]] | None = None,
    ) -> None:
        self.catalogs = _FakeCatalogs(catalogs)
        self.schemas = _FakeSchemas(schemas)
        self.tables = _FakeTables(tables, table_descriptions)


@pytest.fixture()
def databricks_client(monkeypatch) -> TestClient:
    """Spin up the API in databricks mode with a fully mocked WorkspaceClient.

    The mock mirrors the workspace structure the developer asked about — many
    catalogs (so the test proves we're not stuck at 2) plus a vault + bronze
    schema under one of them so the snapshot test has real columns to diff.
    """
    catalogs = [
        "edh_unreg_silver_dev_st",
        "edh_unreg_consumption_dev",
        "edh_unreg_bronze_dev_st",
        "edh_unreg_gold_dev_st",
        "system",
    ]
    schemas = {
        "edh_unreg_silver_dev_st": ["bronze", "raw_vault"],
        "edh_unreg_consumption_dev": ["it4it_servicenow"],
    }
    bronze_columns = [
        _col("mrid", "varchar(64)", nullable=False, comment="Primary key"),
        _col("name", "varchar(255)"),
        _col("equipment_type", "varchar(64)"),
        _col("ingestion_dt", "timestamp", partition_index=0),
    ]
    tables = {
        ("edh_unreg_silver_dev_st", "bronze"): [
            _table("conducting_equipment", columns=bronze_columns),
        ],
        ("edh_unreg_silver_dev_st", "raw_vault"): [],
    }
    descriptions = {
        "edh_unreg_silver_dev_st.bronze.conducting_equipment": bronze_columns,
    }

    fake = _FakeWorkspaceClient(catalogs, schemas, tables, descriptions)

    def _fake_get_client(_settings: Any) -> _FakeWorkspaceClient:
        return fake

    monkeypatch.setenv("DWA_API_DISCOVERY_MODE", "databricks")
    monkeypatch.setenv("DWA_API_DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(
        "dbt_builder.api.routers.discovery.databricks_uc.get_workspace_client",
        _fake_get_client,
    )
    databricks_uc.reset_client_cache()
    get_settings.cache_clear()
    set_service(None)
    try:
        yield TestClient(create_app())
    finally:
        set_service(None)
        get_settings.cache_clear()
        databricks_uc.reset_client_cache()


def test_databricks_list_catalogs_returns_all_workspace_catalogs(
    databricks_client: TestClient,
) -> None:
    r = databricks_client.get("/api/discovery/catalogs")
    assert r.status_code == 200, r.text
    catalogs = r.json()["catalogs"]
    # Proves we are NOT capped at the two stub YAML catalogs.
    assert "edh_unreg_bronze_dev_st" in catalogs
    assert "edh_unreg_gold_dev_st" in catalogs
    assert "system" in catalogs
    assert len(catalogs) == 5


def test_databricks_list_schemas_uses_uc_rest(databricks_client: TestClient) -> None:
    r = databricks_client.get("/api/discovery/catalogs/edh_unreg_silver_dev_st/schemas")
    assert r.status_code == 200, r.text
    schemas = r.json()["schemas"]
    assert "bronze" in schemas
    assert "raw_vault" in schemas


def test_databricks_list_tables_uses_uc_rest(databricks_client: TestClient) -> None:
    r = databricks_client.get(
        "/api/discovery/catalogs/edh_unreg_silver_dev_st/schemas/bronze/tables"
    )
    assert r.status_code == 200, r.text
    tables = r.json()["tables"]
    assert tables == ["conducting_equipment"]


def test_databricks_snapshot_pulls_columns_from_uc_rest(
    databricks_client: TestClient,
) -> None:
    r = databricks_client.post(
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
    # Bronze schema had one table with four columns — they must appear in the
    # bronze snapshot, including the partition flag for ingestion_dt.
    bronze_tables = data["bronze_snapshot"]["tables"]
    assert len(bronze_tables) == 1
    cols = bronze_tables[0]["columns"]
    by_name = {c["name"]: c for c in cols}
    assert by_name["mrid"]["nullable"] is False
    assert by_name["ingestion_dt"]["is_partition"] is True


def test_databricks_listing_failure_returns_503(monkeypatch) -> None:
    """SDK errors must bubble up as HTTP 503, not crash the app."""

    class _Boom:
        def list(self, *_a: Any, **_kw: Any) -> Any:
            raise RuntimeError("workspace unreachable")

    fake = SimpleNamespace(catalogs=_Boom())

    def _fake_get_client(_settings: Any) -> Any:
        return fake

    monkeypatch.setenv("DWA_API_DISCOVERY_MODE", "databricks")
    monkeypatch.setenv("DWA_API_DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(
        "dbt_builder.api.routers.discovery.databricks_uc.get_workspace_client",
        _fake_get_client,
    )
    databricks_uc.reset_client_cache()
    get_settings.cache_clear()
    set_service(None)
    try:
        client = TestClient(create_app())
        r = client.get("/api/discovery/catalogs")
        assert r.status_code == 503
        assert "Unity Catalog REST" in r.json()["detail"]
    finally:
        set_service(None)
        get_settings.cache_clear()
        databricks_uc.reset_client_cache()
