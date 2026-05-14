"""Guardrail test: the deterministic Steps 1-3 must be idempotent.

Re-running ``inspect_catalog`` → ``read_bronze`` → ``diff`` on the same
inputs must produce a byte-identical ``ChangeSet`` (modulo the
``computed_at`` / ``captured_at`` timestamps, which we strip before
comparison). This is the property the pptx labels "idempotency — critical
for CI/CD"; without this test a future refactor of the diff or the
business-key heuristic could silently drift.
"""

from __future__ import annotations

import json
from datetime import datetime

from dbt_builder.src.ai.pipeline import bronze_reader, catalog_inspector, diff_analyzer


def _list_entities(_catalog: str, _schema: str):
    return [
        ("hub_conducting_equipment", "hub"),
        ("sat_conducting_equipment_details", "sat"),
        ("hub_terminal", "hub"),
    ]


def _describe_vault(_catalog: str, _schema: str, table: str):
    if table == "hub_conducting_equipment":
        return [
            ("hk_conducting_equipment", "string", False, None),
            ("mrid", "string", False, None),
            ("load_dts", "timestamp", False, None),
        ]
    if table == "sat_conducting_equipment_details":
        return [
            ("hk_conducting_equipment", "string", False, None),
            ("hashdiff_ce_details", "string", False, None),
            ("name", "string", True, None),
            ("manufacturer", "string", True, None),
            ("load_dts", "timestamp", False, None),
        ]
    if table == "hub_terminal":
        return [
            ("hk_terminal", "string", False, None),
            ("mrid", "string", False, None),
            ("load_dts", "timestamp", False, None),
        ]
    return []


def _list_bronze(_catalog: str, _schema: str):
    return ["conducting_equipment", "terminals", "connectivity_nodes"]


def _describe_bronze(_catalog: str, _schema: str, table: str):
    if table == "conducting_equipment":
        return [
            ("mrid", "string", False, None, False),
            ("name", "string", True, None, False),
            ("manufacturer", "string", True, None, False),
            ("voltage_level", "double", True, None, False),  # NEW column → drift
        ]
    if table == "terminals":
        return [
            ("mrid", "string", False, None, False),
            ("conducting_equipment_mrid", "string", False, None, False),
            ("connectivity_node_mrid", "string", False, None, False),
        ]
    if table == "connectivity_nodes":
        return [
            ("mrid", "string", False, None, False),
            ("description", "string", True, None, False),
        ]
    return []


def _strip_timestamps(payload: dict) -> dict:
    """Recursively drop *_at fields so two runs at different times compare equal."""
    if isinstance(payload, dict):
        return {
            k: _strip_timestamps(v)
            for k, v in payload.items()
            if not k.endswith("_at") and not isinstance(v, datetime)
        }
    if isinstance(payload, list):
        return [_strip_timestamps(v) for v in payload]
    return payload


def _run_pipeline():
    snap = catalog_inspector.inspect_catalog(
        catalog="edh_unreg_silver_dev_st",
        schema_name="raw_vault",
        list_entities=_list_entities,
        describe_table=_describe_vault,
    )
    bronze = bronze_reader.read_bronze(
        catalog="edh_unreg_silver_dev_st",
        schema_name="bronze",
        list_tables=_list_bronze,
        describe_table=_describe_bronze,
    )
    return diff_analyzer.diff(snap, bronze)


def test_diff_is_byte_identical_across_runs():
    first = _run_pipeline().model_dump(mode="json")
    second = _run_pipeline().model_dump(mode="json")
    assert _strip_timestamps(first) == _strip_timestamps(second)


def test_diff_categories_match_expectations():
    change_set = _run_pipeline()
    by_table = {c.table_name: c.category.value for c in change_set.changes}
    # conducting_equipment has a new column -> drift
    assert by_table["conducting_equipment"] == "drift"
    # terminals has no matching vault entity -> new
    assert by_table["terminals"] == "new"
    # connectivity_nodes has no matching vault entity -> new
    assert by_table["connectivity_nodes"] == "new"


def test_diff_change_set_is_json_serialisable():
    change_set = _run_pipeline()
    assert json.loads(change_set.model_dump_json())
