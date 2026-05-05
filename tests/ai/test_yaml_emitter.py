"""Tests for the ModelingPlan -> YAML emitter."""

from __future__ import annotations

import pytest
import yaml

pytestmark = pytest.mark.ai

from dbt_builder.src.ai.contracts.decisions import (  # noqa: E402
    DecisionConfidence,
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.contracts.payloads import SourceSystem  # noqa: E402
from dbt_builder.src.ai.rendering import render_plan, write_plan  # noqa: E402


def _system() -> SourceSystem:
    return SourceSystem(
        system_id="iec_cim",
        system_name="IEC61968_CIM",
        source_type="delta",
        catalog="edh_unreg_silver_dev_st",
        schema_name="bronze",
        record_source="IEC61968_CIM_v2.0",
    )


def _plan() -> ModelingPlan:
    return ModelingPlan(
        system_id="iec_cim",
        hubs=(
            HubDecision(
                name="hub_conducting_equipment",
                source_table="conducting_equipment",
                business_keys=("mrid",),
                hash_key="HK_CONDUCTING_EQUIPMENT",
                confidence=DecisionConfidence.HIGH,
            ),
            HubDecision(
                name="hub_terminal",
                source_table="terminals",
                business_keys=("mrid",),
                hash_key="HK_TERMINAL",
            ),
        ),
        links=(
            LinkDecision(
                name="lnk_terminal_equipment",
                source_table="terminals",
                hash_key="HK_TERMINAL_EQUIPMENT",
                fk_columns=("HK_TERMINAL", "HK_CONDUCTING_EQUIPMENT"),
            ),
        ),
        satellites=(
            SatelliteDecision(
                name="sat_conducting_equipment_details",
                source_table="conducting_equipment",
                parent_hub="hub_conducting_equipment",
                hash_key="HK_CONDUCTING_EQUIPMENT",
                hashdiff="HASHDIFF_CE_DETAILS",
                payload=("name", "equipment_type"),
            ),
        ),
    )


def _render() -> dict:
    return yaml.safe_load(render_plan(_plan(), _system()))


def test_render_returns_valid_yaml() -> None:
    doc = _render()
    assert isinstance(doc, dict)
    assert set(doc) >= {"system", "packages", "macros", "hubs", "satellites", "links", "staging"}


def test_system_block_carries_source_metadata() -> None:
    sys_block = _render()["system"]
    assert sys_block["system_id"] == "iec_cim"
    assert sys_block["catalog"] == "edh_unreg_silver_dev_st"
    assert sys_block["schema"] == "bronze"
    assert sys_block["record_source"] == "IEC61968_CIM_v2.0"
    assert sys_block["record_source_column"] == "RECORD_SOURCE"
    assert sys_block["default_ldts"] == "LOAD_DATE"


def test_hub_block_uses_scalar_business_key_for_singletons() -> None:
    doc = _render()
    hub = next(h for h in doc["hubs"] if h["name"] == "hub_conducting_equipment")
    assert hub["business_key"] == "mrid"
    assert hub["staging_model"] == "stg_conducting_equipment"
    assert hub["hash_key"] == "HK_CONDUCTING_EQUIPMENT"


def test_hub_block_uses_list_for_composite_business_key() -> None:
    plan = ModelingPlan(
        system_id="x",
        hubs=(
            HubDecision(
                name="hub_composite",
                source_table="t",
                business_keys=("a", "b"),
                hash_key="HK_COMPOSITE",
            ),
        ),
    )
    doc = yaml.safe_load(render_plan(plan, SourceSystem(system_id="x", system_name="X")))
    assert doc["hubs"][0]["business_key"] == ["a", "b"]


def test_satellite_block_defaults_effective_from() -> None:
    sat = _render()["satellites"][0]
    assert sat["effective_from"] == "EFFECTIVE_FROM"
    assert sat["payload"] == ["name", "equipment_type"]
    assert sat["source_model"] == "stg_conducting_equipment"
    assert sat["parent_hub"] == "hub_conducting_equipment"


def test_link_block_lists_fk_columns_in_order() -> None:
    link = _render()["links"][0]
    assert link["name"] == "lnk_terminal_equipment"
    assert link["fk_columns"] == ["HK_TERMINAL", "HK_CONDUCTING_EQUIPMENT"]
    assert link["source_model"] == "stg_terminals"


def test_staging_includes_one_block_per_source_table() -> None:
    staging = _render()["staging"]
    names = [s["name"] for s in staging]
    assert names == ["stg_conducting_equipment", "stg_terminals"]


def test_staging_hashed_columns_combine_hub_keys_and_sat_hashdiffs() -> None:
    staging = _render()["staging"]
    ce = next(s for s in staging if s["name"] == "stg_conducting_equipment")
    assert ce["hashed_columns"]["HK_CONDUCTING_EQUIPMENT"] == ["mrid"]
    hd = ce["hashed_columns"]["HASHDIFF_CE_DETAILS"]
    assert hd["is_hashdiff"] is True
    assert hd["columns"] == ["name", "equipment_type"]


def test_render_is_deterministic() -> None:
    a = render_plan(_plan(), _system())
    b = render_plan(_plan(), _system())
    assert a == b


def test_render_rejects_system_id_mismatch() -> None:
    plan = _plan()
    other = SourceSystem(system_id="other", system_name="Other")
    with pytest.raises(ValueError, match="does not match"):
        render_plan(plan, other)


def test_write_plan_writes_file(tmp_path) -> None:
    out = tmp_path / "metadata" / "out.yaml"
    written = write_plan(_plan(), _system(), out)
    assert written == out
    assert out.exists()
    parsed = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert parsed["system"]["system_id"] == "iec_cim"
