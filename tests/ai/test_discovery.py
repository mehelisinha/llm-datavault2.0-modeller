"""Unit tests for ai.discovery (schema_discovery + column_profiler)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from dbt_builder.src.ai.contracts.payloads import InferredType
from dbt_builder.src.ai.discovery import (
    discover_from_dict,
    discover_from_yaml,
    profile_column,
    profile_table,
)

# --- schema_discovery --------------------------------------------------------


def test_discover_from_dict_minimal():
    payload = discover_from_dict(
        {
            "system": {"system_id": "S1", "system_name": "S1"},
            "tables": [
                {
                    "name": "t1",
                    "columns": [
                        {"name": "id", "raw_dtype": "bigint", "nullable": False},
                        {"name": "name", "raw_dtype": "varchar(64)"},
                    ],
                }
            ],
        }
    )
    assert payload.system.system_id == "S1"
    assert len(payload.tables) == 1
    cols = payload.tables[0].columns
    assert cols[0].inferred_type is InferredType.INTEGER
    assert cols[0].nullable is False
    assert cols[1].inferred_type is InferredType.STRING


def test_discover_inherits_catalog_and_schema_from_system():
    payload = discover_from_dict(
        {
            "system": {
                "system_id": "S",
                "system_name": "S",
                "catalog": "cat",
                "schema": "bronze",  # legacy YAML key
            },
            "tables": [{"name": "t", "columns": []}],
        }
    )
    table = payload.tables[0]
    assert table.catalog == "cat"
    assert table.schema_name == "bronze"


def test_discover_table_can_override_system_catalog():
    payload = discover_from_dict(
        {
            "system": {
                "system_id": "S",
                "system_name": "S",
                "catalog": "default_cat",
            },
            "tables": [
                {"name": "t", "catalog": "override", "columns": []},
            ],
        }
    )
    assert payload.tables[0].catalog == "override"


def test_discover_rejects_missing_system():
    with pytest.raises(ValueError, match="system"):
        discover_from_dict({"tables": []})


def test_discover_rejects_column_without_dtype():
    with pytest.raises(ValueError, match="raw_dtype"):
        discover_from_dict(
            {
                "system": {"system_id": "S", "system_name": "S"},
                "tables": [{"name": "t", "columns": [{"name": "x"}]}],
            }
        )


def test_discover_from_yaml_round_trip(tmp_path: Path):
    yaml_text = dedent(
        """
        system:
          system_id: S
          system_name: S
          catalog: cat
          schema: bronze
        tables:
          - name: t
            columns:
              - {name: id, raw_dtype: bigint, nullable: false}
        """
    ).strip()
    yaml_path = tmp_path / "meta.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    payload = discover_from_yaml(yaml_path)
    assert payload.tables[0].columns[0].inferred_type is InferredType.INTEGER


def test_discover_from_yaml_missing_file():
    with pytest.raises(FileNotFoundError):
        discover_from_yaml("/nonexistent/path/x.yaml")


# --- column_profiler ---------------------------------------------------------


def test_profile_column_basic_stats():
    profile = profile_column([1, 2, 2, None, 3])
    assert profile.row_count == 5
    assert profile.null_count == 1
    assert profile.distinct_count == 3
    assert profile.null_rate == pytest.approx(0.2)
    assert profile.cardinality_ratio == pytest.approx(0.75)
    assert profile.is_likely_key is False


def test_profile_column_detects_likely_key():
    profile = profile_column(range(100))
    assert profile.is_likely_key is True
    assert profile.cardinality_ratio == 1.0
    assert profile.null_rate == 0.0


def test_profile_column_handles_empty_iterable():
    profile = profile_column([])
    assert profile.row_count == 0
    assert profile.null_rate == 0.0
    assert profile.cardinality_ratio == 0.0
    assert profile.is_likely_key is False


def test_profile_column_handles_unhashable_values():
    # dict and list are unhashable; profiler must not crash on JSON-style cols.
    profile = profile_column([{"a": 1}, {"a": 2}, {"a": 1}])
    assert profile.row_count == 3
    assert profile.distinct_count == 2  # via str() fallback


def test_profile_column_keeps_distinct_samples_in_order():
    profile = profile_column(["a", "a", "b", "c", "b", "d"], sample_value_count=3)
    assert profile.sample_values == ("a", "b", "c")


def test_profile_column_rejects_negative_sample_count():
    with pytest.raises(ValueError):
        profile_column([1], sample_value_count=-1)


def test_profile_table_populates_only_requested_columns():
    payload = discover_from_dict(
        {
            "system": {"system_id": "S", "system_name": "S"},
            "tables": [
                {
                    "name": "t",
                    "columns": [
                        {"name": "id", "raw_dtype": "bigint"},
                        {"name": "name", "raw_dtype": "varchar(64)"},
                    ],
                }
            ],
        }
    )
    table = payload.tables[0]
    rows = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
    profiled = profile_table(table, rows, columns=["id"])

    assert profiled.profiled_row_count == 2
    assert profiled.columns[0].profile is not None
    assert profiled.columns[0].profile.is_likely_key is True
    assert profiled.columns[1].profile is None  # not requested


def test_profile_table_does_not_mutate_input():
    payload = discover_from_dict(
        {
            "system": {"system_id": "S", "system_name": "S"},
            "tables": [
                {"name": "t", "columns": [{"name": "id", "raw_dtype": "int"}]},
            ],
        }
    )
    original = payload.tables[0]
    profile_table(original, [{"id": 1}])
    assert original.profiled_row_count is None
    assert original.columns[0].profile is None
