"""Tests for the discovery filter that hides DWA's metadata catalog/schema."""

from __future__ import annotations

from dbt_builder.api.routers.discovery import _hide_metadata_catalog, _hide_metadata_schema
from dbt_builder.api.settings import ApiSettings


def _settings(**overrides) -> ApiSettings:
    return ApiSettings(
        discovery_mode="stub",
        metadata_delta_catalog=overrides.get("catalog"),
        metadata_delta_schema=overrides.get("schema"),
        hide_metadata_from_discovery=overrides.get("hide", True),
    )


def test_hide_metadata_catalog_filters_when_enabled():
    s = _settings(catalog="dwa_meta")
    assert _hide_metadata_catalog(s, ("a", "dwa_meta", "b")) == ("a", "b")


def test_hide_metadata_catalog_is_case_insensitive():
    s = _settings(catalog="DWA_meta")
    assert _hide_metadata_catalog(s, ("a", "dwa_meta", "b")) == ("a", "b")


def test_hide_metadata_catalog_noop_when_disabled():
    s = _settings(catalog="dwa_meta", hide=False)
    assert _hide_metadata_catalog(s, ("a", "dwa_meta")) == ("a", "dwa_meta")


def test_hide_metadata_catalog_noop_when_unconfigured():
    s = _settings()
    assert _hide_metadata_catalog(s, ("a", "b")) == ("a", "b")


def test_hide_metadata_schema_only_fires_for_metadata_catalog():
    s = _settings(catalog="edh_unreg_consumption_dev", schema="_dwa_meta")
    # Same catalog → schema filtered.
    assert _hide_metadata_schema(
        s, "edh_unreg_consumption_dev", ("public", "_dwa_meta", "sales")
    ) == ("public", "sales")
    # Different catalog → unchanged.
    assert _hide_metadata_schema(s, "other_catalog", ("public", "_dwa_meta")) == (
        "public",
        "_dwa_meta",
    )


def test_hide_metadata_schema_noop_when_disabled():
    s = _settings(catalog="c", schema="_dwa_meta", hide=False)
    assert _hide_metadata_schema(s, "c", ("_dwa_meta", "x")) == ("_dwa_meta", "x")


def test_hide_metadata_schema_noop_when_schema_unconfigured():
    s = _settings(catalog="c")
    assert _hide_metadata_schema(s, "c", ("_dwa_meta", "x")) == ("_dwa_meta", "x")
