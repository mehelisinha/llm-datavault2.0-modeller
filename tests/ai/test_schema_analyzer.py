"""Tests for the SchemaAnalyzer agent (Phase B / Step 4)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from dbt_builder.src.ai.agents import (
    SchemaAnalyzer,
    SchemaAnalyzerError,
    bronze_table_to_source_table,
)
from dbt_builder.src.ai.contracts.catalog import (
    BronzeColumn,
    BronzeSnapshot,
    BronzeTable,
    ChangeCategory,
    ChangeSet,
    TableChange,
)
from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    HubDecision,
    ModelingPlan,
)
from dbt_builder.src.ai.contracts.payloads import (
    DiscoveryPayload,
    InferredType,
    SourceSystem,
)


def _bronze_table(name: str, *, columns: tuple[BronzeColumn, ...]) -> BronzeTable:
    return BronzeTable(
        catalog="edh_unreg_silver_dev_st",
        schema_name="bronze",
        name=name,
        columns=columns,
        business_key="mrid" if any(c.name == "mrid" for c in columns) else None,
    )


def _bronze_snapshot(*tables: BronzeTable) -> BronzeSnapshot:
    return BronzeSnapshot(
        catalog="edh_unreg_silver_dev_st",
        schema_name="bronze",
        captured_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        tables=tables,
    )


def _change_set(*changes: TableChange) -> ChangeSet:
    return ChangeSet(
        catalog="edh_unreg_silver_dev_st",
        schema_name="raw_vault",
        computed_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        changes=changes,
    )


def _system() -> SourceSystem:
    return SourceSystem(
        system_id="iec_cim",
        system_name="IEC CIM",
        source_type="delta",
        catalog="edh_unreg_silver_dev_st",
        schema_name="bronze",
        record_source="iec_cim",
    )


def _stub_propose(payload: DiscoveryPayload) -> ModelingPlan:
    """Deterministic stub — proposes one hub per table."""
    return ModelingPlan(
        system_id=payload.system.system_id,
        hubs=tuple(
            HubDecision(
                name=f"hub_{t.name}",
                business_keys=(t.columns[0].name,),
                source_table=t.name,
                hash_key=f"HK_{t.name.upper()}",
                confidence=DecisionConfidence.HIGH,
                rationale="stub",
            )
            for t in payload.tables
        ),
        links=(),
        satellites=(),
    )


# ── adapter ─────────────────────────────────────────────────────────────────


def test_bronze_table_to_source_table_preserves_columns_and_order() -> None:
    bronze = _bronze_table(
        "terminals",
        columns=(
            BronzeColumn(name="mrid", raw_dtype="string", nullable=False),
            BronzeColumn(name="seq", raw_dtype="bigint"),
            BronzeColumn(name="ts", raw_dtype="timestamp"),
        ),
    )
    src = bronze_table_to_source_table(bronze)
    assert tuple(c.name for c in src.columns) == ("mrid", "seq", "ts")
    assert tuple(c.ordinal_position for c in src.columns) == (0, 1, 2)


def test_bronze_table_to_source_table_infers_types() -> None:
    bronze = _bronze_table(
        "x",
        columns=(
            BronzeColumn(name="a", raw_dtype="varchar(64)"),
            BronzeColumn(name="b", raw_dtype="bigint"),
            BronzeColumn(name="c", raw_dtype="double"),
            BronzeColumn(name="d", raw_dtype="boolean"),
            BronzeColumn(name="e", raw_dtype="timestamp"),
            BronzeColumn(name="f", raw_dtype="struct<x:int>"),
            BronzeColumn(name="g", raw_dtype="weird_custom_type"),
        ),
    )
    src = bronze_table_to_source_table(bronze)
    by_name = {c.name: c.inferred_type for c in src.columns}
    assert by_name == {
        "a": InferredType.STRING,
        "b": InferredType.INTEGER,
        "c": InferredType.FLOAT,
        "d": InferredType.BOOLEAN,
        "e": InferredType.TIMESTAMP,
        "f": InferredType.JSON,
        "g": InferredType.UNKNOWN,
    }


# ── selection / skip predicate ─────────────────────────────────────────────


def test_select_actionable_skips_unchanged_and_orphaned() -> None:
    cols = (BronzeColumn(name="mrid", raw_dtype="string"),)
    bronze = _bronze_snapshot(
        _bronze_table("a", columns=cols),
        _bronze_table("b", columns=cols),
        _bronze_table("c", columns=cols),
    )
    cs = _change_set(
        TableChange(table_name="a", category=ChangeCategory.NEW),
        TableChange(table_name="b", category=ChangeCategory.UNCHANGED),
        TableChange(table_name="c", category=ChangeCategory.DRIFT),
    )
    analyzer = SchemaAnalyzer(propose_fn=_stub_propose)
    actionable = analyzer.select_actionable(bronze, cs)
    assert tuple(t.name for t in actionable) == ("a", "c")


def test_select_actionable_skips_tables_missing_from_changeset() -> None:
    cols = (BronzeColumn(name="mrid", raw_dtype="string"),)
    bronze = _bronze_snapshot(_bronze_table("ghost", columns=cols))
    analyzer = SchemaAnalyzer(propose_fn=_stub_propose)
    assert analyzer.select_actionable(bronze, _change_set()) == ()


def test_custom_skip_predicate_overrides_default() -> None:
    cols = (BronzeColumn(name="mrid", raw_dtype="string"),)
    bronze = _bronze_snapshot(
        _bronze_table("keep", columns=cols),
        _bronze_table("drop", columns=cols),
    )
    cs = _change_set(
        TableChange(table_name="keep", category=ChangeCategory.NEW),
        TableChange(table_name="drop", category=ChangeCategory.NEW),
    )
    # Skip anything whose name starts with "drop", regardless of category.
    analyzer = SchemaAnalyzer(
        propose_fn=_stub_propose,
        skip_predicate=lambda t, _c: t.name.startswith("drop"),
    )
    assert tuple(t.name for t in analyzer.select_actionable(bronze, cs)) == ("keep",)


def test_selection_is_deterministic_across_runs() -> None:
    cols = (BronzeColumn(name="mrid", raw_dtype="string"),)
    bronze = _bronze_snapshot(
        _bronze_table("a", columns=cols),
        _bronze_table("b", columns=cols),
    )
    cs = _change_set(
        TableChange(table_name="a", category=ChangeCategory.NEW),
        TableChange(table_name="b", category=ChangeCategory.DRIFT),
    )
    analyzer = SchemaAnalyzer(propose_fn=_stub_propose)
    a = analyzer.select_actionable(bronze, cs)
    b = analyzer.select_actionable(bronze, cs)
    assert a == b


# ── payload + analyze ──────────────────────────────────────────────────────


def test_build_payload_raises_when_nothing_actionable() -> None:
    cols = (BronzeColumn(name="mrid", raw_dtype="string"),)
    bronze = _bronze_snapshot(_bronze_table("a", columns=cols))
    cs = _change_set(TableChange(table_name="a", category=ChangeCategory.UNCHANGED))
    analyzer = SchemaAnalyzer(propose_fn=_stub_propose)
    with pytest.raises(SchemaAnalyzerError):
        analyzer.build_payload(system=_system(), bronze=bronze, change_set=cs)


def test_analyze_round_trip_with_stub_modeller() -> None:
    cols = (BronzeColumn(name="mrid", raw_dtype="string"),)
    bronze = _bronze_snapshot(
        _bronze_table("terminals", columns=cols),
        _bronze_table("legacy", columns=cols),
    )
    cs = _change_set(
        TableChange(table_name="terminals", category=ChangeCategory.NEW),
        TableChange(table_name="legacy", category=ChangeCategory.UNCHANGED),
    )
    analyzer = SchemaAnalyzer(propose_fn=_stub_propose)
    plan = analyzer.analyze(system=_system(), bronze=bronze, change_set=cs)
    assert {h.name for h in plan.hubs} == {"hub_terminals"}
    assert plan.system_id == "iec_cim"


def test_from_modeller_binds_propose_method() -> None:
    cols = (BronzeColumn(name="mrid", raw_dtype="string"),)
    bronze = _bronze_snapshot(_bronze_table("x", columns=cols))
    cs = _change_set(TableChange(table_name="x", category=ChangeCategory.NEW))

    class _Stub:
        def __init__(self) -> None:
            self.calls: list[DiscoveryPayload] = []

        def propose(self, payload: DiscoveryPayload) -> ModelingPlan:
            self.calls.append(payload)
            return _stub_propose(payload)

    stub = _Stub()
    analyzer = SchemaAnalyzer.from_modeller(stub)
    analyzer.analyze(system=_system(), bronze=bronze, change_set=cs)
    assert len(stub.calls) == 1
    assert stub.calls[0].tables[0].name == "x"


def test_propose_fn_required() -> None:
    with pytest.raises(ValueError):
        SchemaAnalyzer(propose_fn=None)  # type: ignore[arg-type]
