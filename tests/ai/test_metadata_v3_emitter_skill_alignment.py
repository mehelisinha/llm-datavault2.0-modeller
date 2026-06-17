"""Tests that the v3 emitter follows the DV2 Business/Raw Vault skill rules.

Covers the skill-alignment changes: the ``as_of_dates`` section, AS_OF_DATE
(never SNAPSHOT_DATE) as the PIT snapshot column, and hub stats indexing = 4.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ai

from dbt_builder.src.ai.contracts.bv import BvProposal, PitTable  # noqa: E402
from dbt_builder.src.ai.contracts.decisions import (  # noqa: E402
    DecisionConfidence,
    HubDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.contracts.payloads import SourceSystem  # noqa: E402
from dbt_builder.src.ai.rendering import databricks_defaults as db  # noqa: E402
from dbt_builder.src.ai.rendering.metadata_v3_emitter import (  # noqa: E402
    build_document,
    render_v3,
)


def _system() -> SourceSystem:
    return SourceSystem(system_id="iec_cim", system_name="IEC CIM", source_type="delta")


def _plan_with_pit() -> tuple[ModelingPlan, BvProposal]:
    hub = HubDecision(
        name="hub_terminal",
        business_keys=("mrid",),
        source_table="terminal",
        hash_key="HK_TERMINAL",
        confidence=DecisionConfidence.HIGH,
        rationale="t",
    )
    sats = (
        SatelliteDecision(
            name="sat_terminal_details",
            source_table="terminal",
            parent_hub="hub_terminal",
            hash_key="HK_TERMINAL",
            hashdiff="HASHDIFF_SAT_TERMINAL_DETAILS",
            payload=("col_a",),
            confidence=DecisionConfidence.MEDIUM,
            rationale="t",
        ),
        SatelliteDecision(
            name="sat_terminal_status",
            source_table="terminal",
            parent_hub="hub_terminal",
            hash_key="HK_TERMINAL",
            hashdiff="HASHDIFF_SAT_TERMINAL_STATUS",
            payload=("col_b",),
            confidence=DecisionConfidence.MEDIUM,
            rationale="t",
        ),
    )
    plan = ModelingPlan(system_id="iec_cim", hubs=(hub,), satellites=sats, links=())
    bv = BvProposal(
        system_id="iec_cim",
        pit_tables=(
            PitTable(
                name="pit_terminal",
                parent_hub="hub_terminal",
                satellites=("sat_terminal_details", "sat_terminal_status"),
            ),
        ),
    )
    return plan, bv


def test_as_of_dates_section_emitted_for_pit() -> None:
    plan, bv = _plan_with_pit()
    doc = build_document(plan, _system(), bv)
    assert "as_of_dates" in doc
    aod = doc["as_of_dates"][0]
    assert aod["name"] == "as_of_dates_iec_cim"
    assert aod["date_column"] == "AS_OF_DATE"
    assert aod["primary_hub"] == "hub_terminal"


def test_pit_references_as_of_dates_with_consistent_column() -> None:
    plan, bv = _plan_with_pit()
    doc = build_document(plan, _system(), bv)
    pit = doc["pit_tables"][0]
    assert pit["as_of_dates_table"]["name"] == "as_of_dates_iec_cim"
    assert pit["as_of_dates_table"]["date_column"] == "AS_OF_DATE"
    # PIT clustering + stats use AS_OF_DATE, never SNAPSHOT_DATE.
    assert "AS_OF_DATE" in pit["databricks_config"]["cluster_by"]


def test_no_snapshot_date_anywhere_in_rendered_yaml() -> None:
    plan, bv = _plan_with_pit()
    text = render_v3(plan, _system(), bv)
    assert "SNAPSHOT_DATE" not in text
    assert "AS_OF_DATE" in text


def test_hub_indexes_four_stats_columns() -> None:
    cfg = db.hub_config("HK_TERMINAL")
    assert cfg["table_properties"]["delta.dataSkippingNumIndexedCols"] == 4
    # Non-hub entities keep the default 8.
    assert (
        db.satellite_config("HK_TERMINAL", "HD_X")["table_properties"][
            "delta.dataSkippingNumIndexedCols"
        ]
        == 8
    )


def test_global_optimization_lists_as_of_dates_strategy() -> None:
    strategies = db.global_optimization()["incremental_strategy_defaults"]
    assert strategies["as_of_dates"] == "view"
