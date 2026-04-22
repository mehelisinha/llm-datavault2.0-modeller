"""
Unit tests for MetadataReader.

Tests cover:
- YAML loading and top-level validation
- Hub object creation
- Link object creation
- Satellite object creation (with and without effective_from)
- get_all_components ordering
- Error handling for missing keys and missing file
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import yaml

# Make sure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dv_components.components.sql.raw_vault.hub import HubComponent
from dv_components.components.sql.raw_vault.link import LinkComponent
from dv_components.components.sql.raw_vault.satellite import SatComponent
from poc.metadata.reader import MetadataReader

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_VALID_CONFIG = {
    "system": {
        "system_id": "TEST_001",
        "system_name": "Test System",
        "source_type": "delta",
        "catalog": "test_catalog",
        "schema": "bronze",
        "load_frequency": "daily",
        "record_source": "TEST_SRC",
    },
    "hubs": [
        {
            "name": "hub_order",
            "source_table": "orders",
            "staging_model": "stg_orders",
            "business_key": "order_nk",
            "hash_key": "HK_ORDER",
        }
    ],
    "satellites": [
        {
            "name": "sat_order_details",
            "parent_hub": "hub_order",
            "source_model": "stg_orders",
            "hash_key": "HK_ORDER",
            "hashdiff": "HD_ORDER_DETAILS",
            "payload": ["qty", "price"],
        }
    ],
    "links": [
        {
            "name": "lnk_order_customer",
            "source_model": "stg_orders",
            "hash_key": "HK_ORDER_CUSTOMER",
            "fk_columns": ["HK_ORDER", "HK_CUSTOMER"],
        }
    ],
}


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """Write the minimal valid config to a temp YAML file and return its path."""
    path = tmp_path / "test_metadata.yaml"
    path.write_text(yaml.safe_dump(MINIMAL_VALID_CONFIG), encoding="utf-8")
    return path


@pytest.fixture
def reader(config_file: Path) -> MetadataReader:
    return MetadataReader(config_file)


# ---------------------------------------------------------------------------
# IEC CIM integration fixture (uses the real project config)
# ---------------------------------------------------------------------------

IEC_CONFIG_PATH = (
    Path(__file__).parent.parent / "src" / "metadata" / "iec_cim_metadata.yaml"
)


@pytest.fixture
def iec_reader() -> MetadataReader:
    """Reader backed by the real iec_cim_metadata.yaml."""
    if not IEC_CONFIG_PATH.exists():
        pytest.skip("iec_cim_metadata.yaml not found — skipping integration test")
    return MetadataReader(IEC_CONFIG_PATH)


# ---------------------------------------------------------------------------
# Loading & validation
# ---------------------------------------------------------------------------


def test_load_valid_config(reader: MetadataReader) -> None:
    assert reader.system["system_id"] == "TEST_001"


def test_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        MetadataReader("/nonexistent/path/metadata.yaml")


def test_missing_top_level_key_raises(tmp_path: Path) -> None:
    bad_config = {k: v for k, v in MINIMAL_VALID_CONFIG.items() if k != "hubs"}
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(bad_config), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required top-level keys"):
        MetadataReader(path)


# ---------------------------------------------------------------------------
# Hub parsing
# ---------------------------------------------------------------------------


def test_get_hubs_returns_hub_objects(reader: MetadataReader) -> None:
    hubs = reader.get_hubs()
    assert len(hubs) == 1
    assert isinstance(hubs[0], HubComponent)


def test_hub_fields(reader: MetadataReader) -> None:
    hub = reader.get_hubs()[0]
    assert hub.name == "hub_order"
    assert hub.src_pk == "HK_ORDER"
    assert hub.src_nk == "order_nk"
    assert hub.source_models == ["stg_orders"]


def test_hub_missing_required_key_raises(tmp_path: Path) -> None:
    bad = dict(MINIMAL_VALID_CONFIG)
    bad["hubs"] = [{"name": "hub_x", "source_table": "x"}]  # missing hash_key etc.
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required keys"):
        MetadataReader(path).get_hubs()


# ---------------------------------------------------------------------------
# Satellite parsing
# ---------------------------------------------------------------------------


def test_get_satellites_returns_satellite_objects(reader: MetadataReader) -> None:
    sats = reader.get_satellites()
    assert len(sats) == 1
    assert isinstance(sats[0], SatComponent)


def test_satellite_fields(reader: MetadataReader) -> None:
    sat = reader.get_satellites()[0]
    assert sat.name == "sat_order_details"
    assert sat.src_pk == "HK_ORDER"
    assert sat.src_hashdiff == "HD_ORDER_DETAILS"
    assert sat.src_payload == ["qty", "price"]
    assert sat.src_eff is None  # no effective_from in minimal config


def test_satellite_with_effective_from(tmp_path: Path) -> None:
    config = dict(MINIMAL_VALID_CONFIG)
    config["satellites"] = [
        {
            "name": "sat_with_eff",
            "parent_hub": "hub_order",
            "source_model": "stg_orders",
            "hash_key": "HK_ORDER",
            "hashdiff": "HD_EFF",
            "effective_from": "EFFECTIVE_FROM",
            "payload": ["status"],
        }
    ]
    path = tmp_path / "eff.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    sat = MetadataReader(path).get_satellites()[0]
    assert sat.src_eff == "EFFECTIVE_FROM"


# ---------------------------------------------------------------------------
# Link parsing
# ---------------------------------------------------------------------------


def test_get_links_returns_link_objects(reader: MetadataReader) -> None:
    links = reader.get_links()
    assert len(links) == 1
    assert isinstance(links[0], LinkComponent)


def test_link_fields(reader: MetadataReader) -> None:
    link = reader.get_links()[0]
    assert link.name == "lnk_order_customer"
    assert link.src_pk == "HK_ORDER_CUSTOMER"
    assert link.src_fk == ["HK_ORDER", "HK_CUSTOMER"]
    assert link.source_models == ["stg_orders"]


# ---------------------------------------------------------------------------
# get_all_components ordering
# ---------------------------------------------------------------------------


def test_all_components_ordering(reader: MetadataReader) -> None:
    components = reader.get_all_components()
    types = [type(c).__name__ for c in components]
    # Hubs come before Links which come before Satellites
    assert types.index("Hub") < types.index("Link")
    assert types.index("Link") < types.index("Satellite")


def test_all_components_count(reader: MetadataReader) -> None:
    assert len(reader.get_all_components()) == 3  # 1 hub + 1 link + 1 satellite


# ---------------------------------------------------------------------------
# IEC CIM integration tests (real config file)
# ---------------------------------------------------------------------------


def test_iec_hubs_count(iec_reader: MetadataReader) -> None:
    assert len(iec_reader.get_hubs()) == 3


def test_iec_satellites_count(iec_reader: MetadataReader) -> None:
    assert len(iec_reader.get_satellites()) == 4


def test_iec_links_count(iec_reader: MetadataReader) -> None:
    assert len(iec_reader.get_links()) == 1


def test_iec_hub_names(iec_reader: MetadataReader) -> None:
    names = {h.name for h in iec_reader.get_hubs()}
    assert names == {
        "hub_conducting_equipment",
        "hub_connectivity_node",
        "hub_terminal",
    }


def test_iec_link_fks(iec_reader: MetadataReader) -> None:
    link = iec_reader.get_links()[0]
    assert link.name == "lnk_terminal_equipment_node"
    assert "HK_CONDUCTING_EQUIPMENT" in link.src_fk
    assert "HK_CONNECTIVITY_NODE" in link.src_fk


def test_iec_sat_effective_from(iec_reader: MetadataReader) -> None:
    sats_with_eff = [s for s in iec_reader.get_satellites() if s.src_eff is not None]
    # All IEC satellites have effective_from
    assert len(sats_with_eff) == 4
