"""Regression tests for catalog_from_yaml — must not fall back to 'unknown'
when the emitter writes system.system_id but no system.catalog."""

from __future__ import annotations

from dbt_builder.src.utils.yaml_store import catalog_from_yaml


def test_uses_system_catalog_when_present():
    yaml_text = "system:\n  catalog: my_catalog\n  system_id: ignored\n"
    assert catalog_from_yaml(yaml_text) == "my_catalog"


def test_falls_back_to_system_id_when_catalog_missing():
    yaml_text = "system:\n  system_id: edh_unreg_consumption_dev\n"
    assert catalog_from_yaml(yaml_text) == "edh_unreg_consumption_dev"


def test_returns_unknown_only_when_both_absent():
    assert catalog_from_yaml("system:\n  source_type: x\n") == "unknown"


def test_handles_malformed_yaml():
    assert catalog_from_yaml("this is not: : valid yaml: [") == "unknown"


def test_rejects_invalid_identifier():
    yaml_text = "system:\n  system_id: 'has spaces!'\n"
    assert catalog_from_yaml(yaml_text) == "unknown"
