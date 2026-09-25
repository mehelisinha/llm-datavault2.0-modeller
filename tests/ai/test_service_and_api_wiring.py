"""Integration tests for DwaService + plans router after Phase B wiring."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from dbt_builder.api import create_app
from dbt_builder.src.ai.agents import (
    BvArchitect,
    SchemaAnalyzer,
    YamlGenerator,
)
from dbt_builder.src.ai.contracts.bv import BvProposal
from dbt_builder.src.ai.contracts.catalog import (
    BronzeColumn,
    BronzeSnapshot,
    BronzeTable,
    ChangeCategory,
    ChangeSet,
    TableChange,
)
from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    HubDecision,
    ModelingPlan,
)
from dbt_builder.src.ai.contracts.payloads import DiscoveryPayload, SourceSystem
from dbt_builder.src.ai.service import (
    DwaService,
    LlmAgentNotConfiguredError,
    set_service,
)

# ── Fixtures ────────────────────────────────────────────────────────────────


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


def _system() -> SourceSystem:
    return SourceSystem(
        system_id="iec_cim",
        system_name="IEC CIM",
        source_type="delta",
        catalog="edh_unreg_silver_dev_st",
        schema_name="bronze",
        record_source="iec_cim",
    )


def _bronze() -> BronzeSnapshot:
    return BronzeSnapshot(
        catalog="edh_unreg_silver_dev_st",
        schema_name="bronze",
        captured_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        tables=(
            BronzeTable(
                catalog="edh_unreg_silver_dev_st",
                schema_name="bronze",
                name="terminals",
                columns=(BronzeColumn(name="mrid", raw_dtype="string", nullable=False),),
                business_key="mrid",
            ),
        ),
    )


def _change_set() -> ChangeSet:
    return ChangeSet(
        catalog="edh_unreg_silver_dev_st",
        schema_name="raw_vault",
        computed_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        changes=(TableChange(table_name="terminals", category=ChangeCategory.NEW),),
    )


@pytest.fixture()
def wired_service(tmp_path) -> DwaService:
    """Service with all Phase B agents wired in."""
    from dbt_builder.src.ai.store import SqliteApprovalStore

    store = SqliteApprovalStore(tmp_path / "approvals.sqlite")
    return DwaService(
        approval_store=store,
        schema_analyzer=SchemaAnalyzer(propose_fn=_stub_propose),
        bv_architect=BvArchitect(),
        yaml_generator=YamlGenerator(),
    )


@pytest.fixture()
def client(wired_service: DwaService) -> TestClient:
    set_service(wired_service)
    try:
        yield TestClient(create_app())
    finally:
        set_service(None)


# ── Service-level wiring ────────────────────────────────────────────────────


def test_service_analyze_round_trip(wired_service: DwaService) -> None:
    plan = wired_service.analyze(system=_system(), bronze=_bronze(), change_set=_change_set())
    assert plan.system_id == "iec_cim"
    assert {h.name for h in plan.hubs} == {"hub_terminals"}


def test_service_analyze_raises_when_unwired(tmp_path) -> None:
    from dbt_builder.src.ai.store import SqliteApprovalStore

    svc = DwaService(approval_store=SqliteApprovalStore(tmp_path / "a.sqlite"))
    with pytest.raises(LlmAgentNotConfiguredError):
        svc.analyze(system=_system(), bronze=_bronze(), change_set=_change_set())


def test_service_architect_bv_is_deterministic(wired_service: DwaService) -> None:
    plan = wired_service.analyze(system=_system(), bronze=_bronze(), change_set=_change_set())
    a = wired_service.architect_bv(plan)
    b = wired_service.architect_bv(plan)
    assert a == b
    assert isinstance(a, BvProposal)


def test_service_generate_yaml_deterministic(wired_service: DwaService) -> None:
    plan = wired_service.analyze(system=_system(), bronze=_bronze(), change_set=_change_set())
    bv = wired_service.architect_bv(plan)
    a = wired_service.generate_yaml(plan=plan, bv=bv)
    b = wired_service.generate_yaml(plan=plan, bv=bv)
    assert a == b


# ── HTTP endpoints ─────────────────────────────────────────────────────────


def test_analyze_endpoint_returns_plan(client: TestClient) -> None:
    body = {
        "system": _system().model_dump(),
        "bronze": _bronze().model_dump(mode="json"),
        "change_set": _change_set().model_dump(mode="json"),
    }
    r = client.post("/api/plans/analyze", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["system_id"] == "iec_cim"
    assert {h["name"] for h in data["hubs"]} == {"hub_terminals"}


def test_analyze_endpoint_returns_503_when_llm_unwired(tmp_path, monkeypatch) -> None:
    from dbt_builder.src.ai.store import SqliteApprovalStore

    set_service(DwaService(approval_store=SqliteApprovalStore(tmp_path / "a.sqlite")))
    try:
        c = TestClient(create_app())
        body = {
            "system": _system().model_dump(),
            "bronze": _bronze().model_dump(mode="json"),
            "change_set": _change_set().model_dump(mode="json"),
        }
        r = c.post("/api/plans/analyze", json=body)
        assert r.status_code == 503, r.text
    finally:
        set_service(None)


def test_architect_bv_endpoint(client: TestClient) -> None:
    plan = ModelingPlan(
        system_id="iec_cim",
        hubs=(
            HubDecision(
                name="hub_terminal",
                business_keys=("mrid",),
                source_table="terminal",
                hash_key="HK_TERMINAL",
                confidence=DecisionConfidence.HIGH,
                rationale="t",
            ),
        ),
    )
    r = client.post("/api/plans/architect-bv", json=plan.model_dump(mode="json"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["system_id"] == "iec_cim"
    # Single-sat hub: no PIT, no bridge.
    assert data["pit_tables"] == []
    assert data["bridge_tables"] == []


def test_generate_endpoint_returns_files(client: TestClient) -> None:
    plan = ModelingPlan(
        system_id="iec_cim",
        hubs=(
            HubDecision(
                name="hub_terminal",
                business_keys=("mrid",),
                source_table="terminal",
                hash_key="HK_TERMINAL",
                confidence=DecisionConfidence.HIGH,
                rationale="t",
            ),
        ),
    )
    body = {"plan": plan.model_dump(mode="json"), "bv": None}
    r = client.post("/api/plans/generate", json=body)
    assert r.status_code == 200, r.text
    files = r.json()["files"]
    assert len(files) == 1
    assert files[0]["path"].endswith("hub_terminal.yml")
    assert "src_pk: HK_TERMINAL" in files[0]["body"]


def test_validate_endpoint_still_works(client: TestClient) -> None:
    # Empty rendered_yaml triggers YAML_SYNTAX or empty-handling; an empty
    # plan (no hubs/sats/links) is structurally valid.
    plan = ModelingPlan(system_id="iec_cim")
    r = client.post(
        "/api/plans/validate",
        json={"plan": plan.model_dump(mode="json")},
    )
    assert r.status_code == 200, r.text
