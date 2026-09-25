"""Tests for SourceSystem metadata normalisation in the pipeline router."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ai

from dbt_builder.api.routers.pipeline import (  # noqa: E402
    PipelineRunRequest,
    _source_system_for,
)


def _req(**over) -> PipelineRunRequest:
    base = dict(
        catalog="edh_unreg_consumption_dev",
        bronze_schema="it4it_servicenow",
        system_id="edh_unreg_consumption_dev",
        system_name="edh_unreg_consumption_dev",
        source_type="edh_unreg_consumption_dev",  # degenerate echo of the catalog
    )
    base.update(over)
    return PipelineRunRequest(**base)


def test_degenerate_source_type_is_normalised_to_delta() -> None:
    sys = _source_system_for(_req())
    assert sys.source_type == "delta"


def test_record_source_defaults_to_catalog_schema() -> None:
    sys = _source_system_for(_req())
    assert sys.record_source == "edh_unreg_consumption_dev.it4it_servicenow"


def test_real_source_type_is_preserved() -> None:
    sys = _source_system_for(_req(source_type="servicenow"))
    assert sys.source_type == "servicenow"


def test_explicit_record_source_is_preserved() -> None:
    sys = _source_system_for(_req(record_source="SNOW_v1.0"))
    assert sys.record_source == "SNOW_v1.0"
