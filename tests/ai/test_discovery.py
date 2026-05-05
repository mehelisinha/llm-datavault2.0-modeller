"""Unit tests for ai.discovery (schema_discovery + column_profiler)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from dbt_builder.src.ai.contracts.payloads import InferredType
from dbt_builder.src.ai.discovery import (
    discover_from_dict,
    discover_from_spark,
    discover_from_yaml,
    is_system_column,
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


# --- system columns ----------------------------------------------------------


def test_is_system_column_recognises_known_names():
    for name in (
        "record_source",
        "RECORD_SOURCE",
        "dl_loaded_at",
        "load_ts",
        "__$start_lsn",
        "__$end_lsn",
        "_dl_ingest",
    ):
        assert is_system_column(name), name


def test_is_system_column_ignores_business_names():
    for name in ("id", "mrid", "customer_name", "amount", ""):
        assert not is_system_column(name), name


def test_discover_auto_flags_system_columns():
    payload = discover_from_dict(
        {
            "system": {"system_id": "S", "system_name": "S"},
            "tables": [
                {
                    "name": "t",
                    "columns": [
                        {"name": "id", "raw_dtype": "bigint"},
                        {"name": "record_source", "raw_dtype": "string"},
                        {"name": "__$start_lsn", "raw_dtype": "binary"},
                    ],
                }
            ],
        }
    )
    cols = {c.name: c for c in payload.tables[0].columns}
    assert cols["id"].is_system is False
    assert cols["record_source"].is_system is True
    assert cols["__$start_lsn"].is_system is True


def test_yaml_can_override_system_flag():
    payload = discover_from_dict(
        {
            "system": {"system_id": "S", "system_name": "S"},
            "tables": [
                {
                    "name": "t",
                    "columns": [
                        # Heuristic would say True; YAML opts back in.
                        {"name": "record_source", "raw_dtype": "string", "is_system": False},
                        # Heuristic would say False; YAML force-flags.
                        {"name": "weird_audit_col", "raw_dtype": "string", "is_system": True},
                    ],
                }
            ],
        }
    )
    cols = {c.name: c for c in payload.tables[0].columns}
    assert cols["record_source"].is_system is False
    assert cols["weird_audit_col"].is_system is True


def test_profile_table_never_flags_system_column_as_key():
    payload = discover_from_dict(
        {
            "system": {"system_id": "S", "system_name": "S"},
            "tables": [
                {
                    "name": "t",
                    "columns": [
                        {"name": "id", "raw_dtype": "bigint"},
                        {"name": "dl_loaded_at", "raw_dtype": "timestamp"},
                    ],
                }
            ],
        }
    )
    rows = [
        {"id": 1, "dl_loaded_at": "2026-05-05T00:00:00"},
        {"id": 2, "dl_loaded_at": "2026-05-05T00:00:01"},
        {"id": 3, "dl_loaded_at": "2026-05-05T00:00:02"},
    ]
    profiled = profile_table(payload.tables[0], rows)
    by_name = {c.name: c for c in profiled.columns}
    # Both columns are perfectly unique in the sample, but only `id` is a key.
    assert by_name["id"].profile.is_likely_key is True
    assert by_name["dl_loaded_at"].profile.is_likely_key is False


# --- spark adapter -----------------------------------------------------------


class _FakeRow:
    def __init__(self, **fields):
        self._fields = fields

    def asDict(self):  # noqa: N802 (Spark API)
        return dict(self._fields)


class _FakeDataFrame:
    def __init__(self, rows):
        self._rows = list(rows)

    def collect(self):
        return list(self._rows)


class _FakeSpark:
    """Tiny stand-in for SparkSession used by discover_from_spark tests."""

    def __init__(self, *, tables, describe):
        self._tables = tables
        self._describe = describe
        self.queries: list[str] = []

    def sql(self, query: str):
        self.queries.append(query)
        if query.startswith("SHOW TABLES"):
            return _FakeDataFrame(
                _FakeRow(tableName=t, isTemporary=False) for t in self._tables
            )
        if query.startswith("DESCRIBE TABLE"):
            # Last token is `catalog.schema.table` quoted with backticks.
            tail = query.rsplit(".", 1)[-1].strip("`")
            return _FakeDataFrame(_FakeRow(**r) for r in self._describe.get(tail, []))
        raise AssertionError(f"unexpected query: {query}")


def test_discover_from_spark_enumerates_and_describes_tables():
    fake = _FakeSpark(
        tables=["customers", "orders"],
        describe={
            "customers": [
                {"col_name": "customer_id", "data_type": "bigint", "comment": None},
                {"col_name": "email", "data_type": "string", "comment": "PII"},
                {"col_name": "record_source", "data_type": "string", "comment": None},
                # Trailing partition-info block that DESCRIBE TABLE adds.
                {"col_name": "", "data_type": "", "comment": None},
                {"col_name": "# Partition Information", "data_type": "", "comment": None},
            ],
            "orders": [
                {"col_name": "order_id", "data_type": "bigint", "comment": None},
                {"col_name": "__$start_lsn", "data_type": "binary", "comment": None},
            ],
        },
    )
    payload = discover_from_spark(
        fake,
        catalog="main",
        schema="bronze",
        system_id="DEMO",
        system_name="Demo",
    )
    assert payload.system.catalog == "main"
    assert payload.system.schema_name == "bronze"
    assert payload.system.record_source == "main.bronze"
    names = [t.name for t in payload.tables]
    assert names == ["customers", "orders"]

    customers = payload.get_table("customers")
    assert customers is not None
    cols = {c.name: c for c in customers.columns}
    assert cols["customer_id"].inferred_type is InferredType.INTEGER
    assert cols["email"].description == "PII"
    assert cols["record_source"].is_system is True
    # Trailing "" / "#..." rows must not become columns.
    assert "" not in cols and "# Partition Information" not in cols

    orders = payload.get_table("orders")
    assert orders is not None
    assert {c.name: c.is_system for c in orders.columns} == {
        "order_id": False,
        "__$start_lsn": True,
    }


def test_discover_from_spark_honours_explicit_table_list():
    fake = _FakeSpark(
        tables=["should_be_ignored"],
        describe={
            "only_one": [{"col_name": "id", "data_type": "int", "comment": None}],
        },
    )
    payload = discover_from_spark(
        fake,
        catalog="c",
        schema="s",
        system_id="X",
        system_name="X",
        tables=["only_one"],
    )
    assert [t.name for t in payload.tables] == ["only_one"]
    # SHOW TABLES must not have been issued.
    assert all(not q.startswith("SHOW TABLES") for q in fake.queries)


def test_discover_from_spark_skips_tables_with_no_columns():
    fake = _FakeSpark(
        tables=["empty", "real"],
        describe={
            "empty": [],
            "real": [{"col_name": "id", "data_type": "int", "comment": None}],
        },
    )
    payload = discover_from_spark(
        fake, catalog="c", schema="s", system_id="X", system_name="X"
    )
    assert [t.name for t in payload.tables] == ["real"]
