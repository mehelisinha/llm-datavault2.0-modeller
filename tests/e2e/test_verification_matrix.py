"""B8 — parametrised API verification matrix."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from dbt_builder.api import create_app
from dbt_builder.api.settings import get_settings
from dbt_builder.src.ai.agents import BvArchitect, SchemaAnalyzer, YamlGenerator
from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    HubDecision,
    ModelingPlan,
)
from dbt_builder.src.ai.contracts.payloads import DiscoveryPayload
from dbt_builder.src.ai.service import DwaService, set_service
from dbt_builder.src.ai.store import SqliteApprovalStore

_MATRIX = yaml.safe_load(
    (Path(__file__).parent / "verification_matrix.yaml").read_text(encoding="utf-8")
)["scenarios"]


def _stub_propose(payload: DiscoveryPayload) -> ModelingPlan:
    return ModelingPlan(
        system_id=payload.system.system_id,
        hubs=tuple(
            HubDecision(
                name=f"hub_{t.name}",
                business_keys=(t.columns[0].name,),
                source_table=t.name,
                hash_key=f"HK_{t.name.upper()}",
                confidence=DecisionConfidence.HIGH,
                rationale="stub",
            )
            for t in payload.tables
        ),
    )


@pytest.fixture()
def matrix_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DWA_API_DISCOVERY_MODE", "stub")
    get_settings.cache_clear()
    store = SqliteApprovalStore(tmp_path / "matrix.sqlite")
    svc = DwaService(
        approval_store=store,
        schema_analyzer=SchemaAnalyzer(propose_fn=_stub_propose),
        bv_architect=BvArchitect(),
        yaml_generator=YamlGenerator(),
    )
    set_service(svc)
    try:
        yield TestClient(create_app())
    finally:
        set_service(None)
        get_settings.cache_clear()


@pytest.fixture()
def snapshot_body(matrix_client: TestClient) -> dict:
    r = matrix_client.post(
        "/api/discovery/snapshot",
        json={
            "catalog": "edh_unreg_silver_dev_st",
            "bronze_schema": "bronze",
            "vault_schema": "raw_vault",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("scenario", _MATRIX, ids=[s["id"] for s in _MATRIX])
def test_verification_matrix_row(
    matrix_client: TestClient,
    snapshot_body: dict,
    scenario: dict,
) -> None:
    method = scenario["method"].upper()
    path = scenario["path"]
    headers = {"X-Actor": "matrix@test"}

    body: dict | None = None
    if scenario.get("use_snapshot"):
        body = {
            "system": snapshot_body["system"],
            "bronze": snapshot_body["bronze_snapshot"],
            "change_set": snapshot_body["change_set"],
        }
    elif scenario.get("use_analyze_plan"):
        analyze = matrix_client.post(
            "/api/plans/analyze",
            json={
                "system": snapshot_body["system"],
                "bronze": snapshot_body["bronze_snapshot"],
                "change_set": snapshot_body["change_set"],
            },
        )
        assert analyze.status_code == 200, analyze.text
        plan = analyze.json()
        body = plan if scenario["id"] == "architect_bv" else {"plan": plan, "bv": None}
    elif "json" in scenario:
        body = scenario["json"]

    if method == "GET":
        response = matrix_client.get(path)
    else:
        response = matrix_client.request(method, path, json=body, headers=headers)

    assert response.status_code == scenario["expect_status"], response.text
