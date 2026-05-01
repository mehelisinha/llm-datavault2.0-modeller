"""Unit tests for ai.contracts.payloads."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dbt_builder.src.ai.contracts.payloads import (
    ColumnProfile,
    DiscoveryPayload,
    InferredType,
    SourceColumn,
    SourceSystem,
    SourceTable,
)

# --- ColumnProfile -----------------------------------------------------------


def test_column_profile_accepts_valid_ratios():
    profile = ColumnProfile(
        row_count=10,
        null_count=2,
        distinct_count=5,
        null_rate=0.2,
        cardinality_ratio=0.625,
        sample_values=("a", "b"),
    )
    assert profile.is_likely_key is False
    assert profile.sample_values == ("a", "b")


@pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0])
def test_column_profile_rejects_out_of_range_ratios(bad: float):
    with pytest.raises(ValidationError):
        ColumnProfile(
            row_count=10,
            null_count=0,
            distinct_count=10,
            null_rate=bad,
            cardinality_ratio=1.0,
        )


def test_column_profile_truncates_long_samples():
    long = "x" * 500
    profile = ColumnProfile(
        row_count=1,
        null_count=0,
        distinct_count=1,
        null_rate=0.0,
        cardinality_ratio=1.0,
        sample_values=(long,),
    )
    assert len(profile.sample_values[0]) == 200


def test_column_profile_is_frozen():
    profile = ColumnProfile(
        row_count=1,
        null_count=0,
        distinct_count=1,
        null_rate=0.0,
        cardinality_ratio=1.0,
    )
    with pytest.raises(ValidationError):
        profile.row_count = 99  # type: ignore[misc]


# --- SourceTable / SourceColumn ----------------------------------------------


def _col(name: str, dtype: str = "varchar(64)") -> SourceColumn:
    return SourceColumn(name=name, raw_dtype=dtype, inferred_type=InferredType.STRING)


def test_source_table_rejects_duplicate_column_names_case_insensitive():
    with pytest.raises(ValidationError):
        SourceTable(name="t", columns=(_col("Name"), _col("name")))


def test_source_table_fully_qualified_name_skips_missing_parts():
    assert SourceTable(name="t", columns=()).fully_qualified_name == "t"
    assert (
        SourceTable(name="t", schema_name="bronze", columns=()).fully_qualified_name == "bronze.t"
    )
    assert (
        SourceTable(name="t", schema_name="bronze", catalog="cat", columns=()).fully_qualified_name
        == "cat.bronze.t"
    )


# --- DiscoveryPayload --------------------------------------------------------


def test_discovery_payload_get_table_supports_bare_and_fqn_lookup():
    sys = SourceSystem(system_id="X", system_name="X")
    payload = DiscoveryPayload(
        system=sys,
        tables=(SourceTable(name="t1", schema_name="bronze", columns=()),),
    )
    assert payload.get_table("t1") is not None
    assert payload.get_table("BRONZE.T1") is not None
    assert payload.get_table("missing") is None


def test_discovery_payload_rejects_duplicate_tables():
    sys = SourceSystem(system_id="X", system_name="X")
    with pytest.raises(ValidationError):
        DiscoveryPayload(
            system=sys,
            tables=(
                SourceTable(name="t", schema_name="bronze", columns=()),
                SourceTable(name="T", schema_name="bronze", columns=()),
            ),
        )


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        SourceColumn(name="c", raw_dtype="int", surprise="boom")  # type: ignore[call-arg]
