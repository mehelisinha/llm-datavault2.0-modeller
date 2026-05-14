"""Guardrail tests for the Validator (Step 6) and the approval gate.

These pin the rules from ``dv-metadata-architect.agent.md`` that the
validator must always enforce, so a future refactor of the rule set can't
silently weaken any of them. Each rule has a positive (passes) and
negative (raises ERROR) case.
"""

from __future__ import annotations

import yaml

from dbt_builder.src.ai.contracts.approval import ApprovalStatus
from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.contracts.validation import Severity
from dbt_builder.src.ai.service import ApprovalGateError, DwaService
from dbt_builder.src.ai.store import SqliteApprovalStore
from dbt_builder.src.ai.validation import validate


def _yaml_with(overrides: dict) -> str:
    base = {
        "system": {"system_id": "demo", "system_name": "demo"},
        "hubs": [{"name": "hub_x", "databricks_config": {"materialized": "incremental"}}],
        "satellites": [
            {
                "name": "sat_x_details",
                "parent_hub": "hub_x",
                "hashdiff": "hashdiff_x_details",
                "payload": ["name"],
                "databricks_config": {"materialized": "incremental"},
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
    base.update(overrides)
    return yaml.safe_dump(base)


# ─── referential integrity rules ─────────────────────────────────────────────


def test_orphan_satellite_is_an_error():
    rendered = _yaml_with(
        {
            "satellites": [
                {
                    "name": "sat_x_details",
                    "parent_hub": "hub_does_not_exist",
                    "hashdiff": "hashdiff_x_details",
                    "payload": ["name"],
                    "databricks_config": {
                        "materialized": "incremental",
                        "on_schema_change": "append_new_columns",
                    },
                }
            ]
        }
    )
    report = validate(rendered_yaml=rendered)
    codes = {i.code for i in report.issues if i.severity is Severity.ERROR}
    assert "ORPHAN_SAT" in codes
    assert not report.passed


def test_undeclared_hashdiff_is_an_error():
    rendered = _yaml_with({"staging": [{"name": "stg_x", "hashed_columns": {}}]})
    report = validate(rendered_yaml=rendered)
    codes = {i.code for i in report.issues if i.severity is Severity.ERROR}
    assert "UNDECLARED_HASHDIFF" in codes


def test_system_column_in_payload_is_an_error():
    rendered = _yaml_with(
        {
            "satellites": [
                {
                    "name": "sat_x_details",
                    "parent_hub": "hub_x",
                    "hashdiff": "hashdiff_x_details",
                    "payload": ["name", "load_dts"],
                    "databricks_config": {
                        "materialized": "incremental",
                        "on_schema_change": "append_new_columns",
                    },
                }
            ]
        }
    )
    report = validate(rendered_yaml=rendered)
    codes = {i.code for i in report.issues if i.severity is Severity.ERROR}
    assert "SYSTEM_COL_IN_PAYLOAD" in codes


def test_append_only_on_eff_sat_is_an_error():
    rendered = _yaml_with(
        {
            "eff_sats": [
                {
                    "name": "eff_sat_x",
                    "databricks_config": {
                        "materialized": "incremental",
                        "incremental_strategy": "merge",
                        "on_schema_change": "append_new_columns",
                        "table_properties": {"delta.appendOnly": True},
                    },
                }
            ]
        }
    )
    report = validate(rendered_yaml=rendered)
    codes = {i.code for i in report.issues if i.severity is Severity.ERROR}
    assert "APPEND_ONLY_FORBIDDEN" in codes


def test_missing_on_schema_change_is_a_warning_not_error():
    rendered = _yaml_with({})  # the default plan omits on_schema_change
    report = validate(rendered_yaml=rendered)
    warnings = {i.code for i in report.issues if i.severity is Severity.WARNING}
    assert "MISSING_ON_SCHEMA_CHANGE" in warnings
    # Warnings alone must not fail the report — approval gate would block on
    # ERROR only.
    assert report.summary.errors == 0


def test_clean_yaml_passes():
    clean = _yaml_with(
        {
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
        }
    )
    report = validate(rendered_yaml=clean)
    assert report.passed
    assert report.summary.errors == 0


# ─── approval gate ───────────────────────────────────────────────────────────


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


def test_approval_gate_blocks_when_validation_has_errors(tmp_path):
    store = SqliteApprovalStore(tmp_path / "approvals.sqlite")
    service = DwaService(approval_store=store)
    plan = _plan()
    bad_yaml = _yaml_with(
        {
            "satellites": [
                {
                    "name": "sat_x_details",
                    "parent_hub": "missing_hub",
                    "hashdiff": "hashdiff_x_details",
                    "payload": ["name"],
                    "databricks_config": {"materialized": "incremental"},
                }
            ]
        }
    )
    report = service.validate(plan=plan, rendered_yaml=bad_yaml)
    service.submit_for_review(
        plan=plan, rendered_yaml=bad_yaml, validation=report, actor="reviewer@example.com"
    )

    try:
        service.approve(plan_id=report.plan_id, actor="reviewer@example.com")
    except ApprovalGateError as exc:
        assert "ERROR" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Approval gate did not block plan with ERROR issues.")


def test_approval_gate_allows_clean_plan(tmp_path):
    store = SqliteApprovalStore(tmp_path / "approvals.sqlite")
    service = DwaService(approval_store=store)
    plan = _plan()
    clean_yaml = _yaml_with(
        {
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
        }
    )
    report = service.validate(plan=plan, rendered_yaml=clean_yaml)
    service.submit_for_review(
        plan=plan, rendered_yaml=clean_yaml, validation=report, actor="reviewer@example.com"
    )
    record = service.approve(plan_id=report.plan_id, actor="reviewer@example.com")
    assert record.status is ApprovalStatus.APPROVED


# ─── audit-trail integrity ───────────────────────────────────────────────────


def test_history_is_append_only_and_versioned(tmp_path):
    store = SqliteApprovalStore(tmp_path / "approvals.sqlite")
    service = DwaService(approval_store=store)
    plan = _plan()
    clean_yaml = _yaml_with(
        {
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
        }
    )
    report = service.validate(plan=plan, rendered_yaml=clean_yaml)
    service.submit_for_review(
        plan=plan, rendered_yaml=clean_yaml, validation=report, actor="user@example.com"
    )
    service.request_changes(
        plan_id=report.plan_id, actor="reviewer@example.com", comment="Tighten BV rules"
    )
    service.approve(plan_id=report.plan_id, actor="lead@example.com")

    history = service.history(report.plan_id)
    assert [r.version for r in history] == [1, 2, 3]
    assert [r.status.value for r in history] == [
        "draft",
        "changes_requested",
        "approved",
    ]
