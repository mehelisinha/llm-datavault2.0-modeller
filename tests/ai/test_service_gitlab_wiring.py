"""DwaService.approve must invoke the GitLab publisher when configured,
and tolerate publisher failures without rolling back the approval.
"""

from __future__ import annotations

import yaml

from dbt_builder.src.ai.contracts.approval import ApprovalStatus
from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.service import DwaService
from dbt_builder.src.ai.store import SqliteApprovalStore


def _yaml() -> str:
    base = {
        "system": {"system_id": "demo", "system_name": "demo", "catalog": "iec"},
        "hubs": [
            {
                "name": "hub_x",
                "databricks_config": {
                    "materialized": "incremental",
                    "on_schema_change": "append_new_columns",
                },
            }
        ],
        "satellites": [
            {
                "name": "sat_x_details",
                "parent_hub": "hub_x",
                "hashdiff": "hashdiff_x_details",
                "payload": ["name"],
                "databricks_config": {
                    "materialized": "incremental",
                    "on_schema_change": "append_new_columns",
                },
            }
        ],
        "staging": [
            {
                "name": "stg_x",
                "hashed_columns": {"hashdiff_x_details": {"is_hashdiff": True}},
            }
        ],
        "eff_sats": [],
        "pit_tables": [],
        "bridge_tables": [],
        "bv_sats": [],
    }
    return yaml.safe_dump(base)


def _plan() -> ModelingPlan:
    return ModelingPlan(
        system_id="demo",
        hubs=(
            HubDecision(name="hub_x", source_table="x", business_keys=("mrid",), hash_key="HK_X"),
        ),
        satellites=(
            SatelliteDecision(
                name="sat_x_details",
                source_table="x",
                parent_hub="hub_x",
                hash_key="HK_X",
                hashdiff="HASHDIFF_X_DETAILS",
                payload=("name",),
            ),
        ),
    )


class _RecordingPublisher:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def publish(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return "https://git.example.com/.../merge_requests/1"


class _ExplodingPublisher:
    def publish(self, **kwargs):  # noqa: D401
        raise RuntimeError("boom")


def test_approve_invokes_publisher_with_catalog_and_version(tmp_path):
    store = SqliteApprovalStore(tmp_path / "a.sqlite")
    pub = _RecordingPublisher()
    service = DwaService(approval_store=store, gitlab_publisher=pub)
    plan = _plan()
    rendered = _yaml()
    report = service.validate(plan=plan, rendered_yaml=rendered)
    service.submit_for_review(
        plan=plan, rendered_yaml=rendered, validation=report, actor="user@example.com"
    )

    record = service.approve(plan_id=report.plan_id, actor="lead@example.com")

    assert record.status is ApprovalStatus.APPROVED
    assert len(pub.calls) == 1
    call = pub.calls[0]
    assert call["catalog"] == "iec"
    assert call["plan_id"] == report.plan_id
    assert call["version"] >= 1
    assert call["actor"] == "lead@example.com"
    assert call["rendered_yaml"] == rendered


def test_publisher_failure_does_not_block_approval(tmp_path):
    store = SqliteApprovalStore(tmp_path / "a.sqlite")
    service = DwaService(approval_store=store, gitlab_publisher=_ExplodingPublisher())
    plan = _plan()
    rendered = _yaml()
    report = service.validate(plan=plan, rendered_yaml=rendered)
    service.submit_for_review(
        plan=plan, rendered_yaml=rendered, validation=report, actor="user@example.com"
    )

    record = service.approve(plan_id=report.plan_id, actor="lead@example.com")

    assert record.status is ApprovalStatus.APPROVED


def test_no_publisher_no_problem(tmp_path):
    store = SqliteApprovalStore(tmp_path / "a.sqlite")
    service = DwaService(approval_store=store)  # publisher unconfigured
    plan = _plan()
    rendered = _yaml()
    report = service.validate(plan=plan, rendered_yaml=rendered)
    service.submit_for_review(
        plan=plan, rendered_yaml=rendered, validation=report, actor="user@example.com"
    )

    record = service.approve(plan_id=report.plan_id, actor="lead@example.com")
    assert record.status is ApprovalStatus.APPROVED
