"""Unit tests for the deterministic sat-split heuristic.

Covers the three-way bucket classifier plus the modeller-prompt hint
builder. The heuristic is the single source of truth for "should we
split this hub into details / operational / measurements satellites?",
so these tests guard against silent regressions in either the regex
catalogue or the recommend-split threshold.
"""

from __future__ import annotations

from dbt_builder.src.ai.agents.sat_split_heuristics import (
    MIN_OPERATIONAL_FOR_SPLIT,
    build_hint,
    classify_columns,
)
from dbt_builder.src.ai.contracts.payloads import (
    ColumnProfile,
    InferredType,
    SourceColumn,
    SourceTable,
)


def _col(
    name: str,
    *,
    itype: InferredType = InferredType.STRING,
    is_system: bool = False,
    cardinality: float | None = None,
) -> SourceColumn:
    profile = None
    if cardinality is not None:
        profile = ColumnProfile(
            row_count=100,
            null_count=0,
            distinct_count=int(cardinality * 100),
            null_rate=0.0,
            cardinality_ratio=cardinality,
            is_likely_key=cardinality >= 0.99,
        )
    return SourceColumn(
        name=name,
        raw_dtype="varchar(64)",
        inferred_type=itype,
        is_system=is_system,
        profile=profile,
    )


def _table(name: str, cols: list[SourceColumn]) -> SourceTable:
    return SourceTable(name=name, columns=tuple(cols))


# ── classify_columns ────────────────────────────────────────────────────────


def test_classify_returns_all_three_keys_even_when_empty() -> None:
    table = _table("empty", [_col("c", is_system=True)])
    out = classify_columns(table)
    assert set(out.keys()) == {"details", "operational", "measurements"}
    assert all(out[k] == [] for k in out)


def test_operational_regex_buckets_status_and_flag_columns() -> None:
    table = _table(
        "device",
        [
            _col("name"),
            _col("status"),
            _col("is_active"),
            _col("connected"),
            _col("alarm_flag"),
        ],
    )
    out = classify_columns(table)
    assert set(out["operational"]) == {"status", "is_active", "connected", "alarm_flag"}
    assert out["details"] == ["name"]


def test_measurement_regex_requires_numeric_inferred_type() -> None:
    table = _table(
        "sensor",
        [
            _col("power_kwh", itype=InferredType.FLOAT),
            # _value suffix but STRING -> falls into details, not measurements
            _col("status_value", itype=InferredType.STRING),
        ],
    )
    out = classify_columns(table)
    assert out["measurements"] == ["power_kwh"]
    assert "status_value" in out["details"]


def test_system_columns_are_excluded_entirely() -> None:
    table = _table(
        "x",
        [
            _col("name"),
            _col("load_dts", is_system=True),
            _col("record_source"),  # SYSTEM_COLUMN_PATTERNS match
            _col("dl_loaded_at"),   # SYSTEM_COLUMN_PATTERNS match
        ],
    )
    out = classify_columns(table)
    assert out == {"details": ["name"], "operational": [], "measurements": []}


def test_key_like_columns_are_dropped_from_payload_buckets() -> None:
    table = _table(
        "asset",
        [
            _col("name"),
            _col("is_unique_id", cardinality=0.99),  # would match operational but is key-like
        ],
    )
    out = classify_columns(table)
    assert out["details"] == ["name"]
    assert out["operational"] == []


def test_excluded_columns_are_honoured_case_insensitive() -> None:
    table = _table("a", [_col("name"), _col("status")])
    out = classify_columns(table, excluded_columns=("NAME",))
    assert out["details"] == []
    assert out["operational"] == ["status"]


# ── build_hint ──────────────────────────────────────────────────────────────


def test_build_hint_recommends_split_at_threshold() -> None:
    # MIN_OPERATIONAL_FOR_SPLIT operational + at least 1 details -> split.
    op_cols = [_col(f"is_x{i}") for i in range(MIN_OPERATIONAL_FOR_SPLIT)]
    table = _table("a", [_col("name"), *op_cols])
    hint = build_hint([table])
    assert hint["a"]["recommend_split"] is True


def test_build_hint_does_not_recommend_split_below_threshold() -> None:
    table = _table("a", [_col("name"), _col("status")])  # 1 op only
    hint = build_hint([table])
    assert hint["a"]["recommend_split"] is False
    assert "no split" in hint["a"]["reason"].lower()


def test_build_hint_recommends_split_for_measurements() -> None:
    table = _table(
        "sensor",
        [
            _col("name"),
            _col("power_kwh", itype=InferredType.FLOAT),
            _col("flow_total", itype=InferredType.FLOAT),
        ],
    )
    hint = build_hint([table])
    assert hint["sensor"]["recommend_split"] is True
