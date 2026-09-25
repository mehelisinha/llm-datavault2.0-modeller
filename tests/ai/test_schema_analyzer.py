"""Tests for the SchemaAnalyzer agent (Phase B / Step 4)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from dbt_builder.src.ai.agents import (
    UNCLASSIFIED_SKIP_REASON,
    BronzeAnalysisSummary,
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


# ── empty-actionable diagnostics ───────────────────────────────────────────


def test_empty_bronze_snapshot_error_distinguishes_empty_schema() -> None:
    """When bronze itself is empty the message must point at the schema, not
    the skip predicate — those are very different operator problems."""
    bronze = _bronze_snapshot()  # zero tables
    analyzer = SchemaAnalyzer(propose_fn=_stub_propose)
    with pytest.raises(SchemaAnalyzerError) as exc_info:
        analyzer.build_payload(system=_system(), bronze=bronze, change_set=_change_set())

    msg = str(exc_info.value)
    assert "empty" in msg.lower()
    # Location is included so operators can see *which* schema is empty.
    assert "edh_unreg_silver_dev_st.bronze" in msg
    # Structured summary is attached even in the empty case.
    summary = exc_info.value.summary
    assert isinstance(summary, BronzeAnalysisSummary)
    assert summary.bronze_total == 0
    assert summary.actionable_count == 0
    assert summary.skipped_count == 0
    assert summary.skipped_by_category == {}


def test_empty_actionable_error_carries_structured_summary() -> None:
    """All-UNCHANGED is the exact symptom the user hit when vault==bronze.
    The error must expose counts + sample names so the UI / orchestrator
    can render a real diagnostic, not just a string."""
    cols = (BronzeColumn(name="mrid", raw_dtype="string"),)
    bronze = _bronze_snapshot(
        _bronze_table("alpha", columns=cols),
        _bronze_table("bravo", columns=cols),
        _bronze_table("charlie", columns=cols),
    )
    cs = _change_set(
        TableChange(table_name="alpha", category=ChangeCategory.UNCHANGED),
        TableChange(table_name="bravo", category=ChangeCategory.UNCHANGED),
        TableChange(table_name="charlie", category=ChangeCategory.UNCHANGED),
    )
    analyzer = SchemaAnalyzer(propose_fn=_stub_propose)
    with pytest.raises(SchemaAnalyzerError) as exc_info:
        analyzer.build_payload(system=_system(), bronze=bronze, change_set=cs)

    summary = exc_info.value.summary
    assert isinstance(summary, BronzeAnalysisSummary)
    assert summary.bronze_total == 3
    assert summary.actionable_count == 0
    assert summary.skipped_count == 3
    assert summary.skipped_by_category == {ChangeCategory.UNCHANGED: 3}
    # Snapshot order is preserved in the sample.
    assert summary.skipped_sample_names[ChangeCategory.UNCHANGED] == ("alpha", "bravo", "charlie")
    # And the rendered message references the location, the count, and the category.
    msg = str(exc_info.value)
    assert "edh_unreg_silver_dev_st.bronze" in msg
    assert "3 bronze tables" in msg
    assert ChangeCategory.UNCHANGED.value in msg
    assert "alpha" in msg


def test_empty_actionable_error_separates_unclassified_from_categories() -> None:
    """A bronze table missing from the change-set must show up under the
    UNCLASSIFIED_SKIP_REASON bucket, not be silently folded into a category."""
    cols = (BronzeColumn(name="mrid", raw_dtype="string"),)
    bronze = _bronze_snapshot(
        _bronze_table("known", columns=cols),
        _bronze_table("unknown", columns=cols),
    )
    cs = _change_set(TableChange(table_name="known", category=ChangeCategory.ORPHANED))
    analyzer = SchemaAnalyzer(propose_fn=_stub_propose)
    with pytest.raises(SchemaAnalyzerError) as exc_info:
        analyzer.build_payload(system=_system(), bronze=bronze, change_set=cs)

    summary = exc_info.value.summary
    assert isinstance(summary, BronzeAnalysisSummary)
    assert summary.skipped_by_category == {
        ChangeCategory.ORPHANED: 1,
        UNCLASSIFIED_SKIP_REASON: 1,
    }
    assert summary.skipped_sample_names[ChangeCategory.ORPHANED] == ("known",)
    assert summary.skipped_sample_names[UNCLASSIFIED_SKIP_REASON] == ("unknown",)


def test_empty_actionable_sample_is_truncated_for_large_skip_lists() -> None:
    """The sample list shows up to a small fixed cap; the count stays exact."""
    cols = (BronzeColumn(name="mrid", raw_dtype="string"),)
    bronze = _bronze_snapshot(*(_bronze_table(f"t{i:02d}", columns=cols) for i in range(20)))
    cs = _change_set(
        *(TableChange(table_name=f"t{i:02d}", category=ChangeCategory.UNCHANGED) for i in range(20))
    )
    analyzer = SchemaAnalyzer(propose_fn=_stub_propose)
    with pytest.raises(SchemaAnalyzerError) as exc_info:
        analyzer.build_payload(system=_system(), bronze=bronze, change_set=cs)

    summary = exc_info.value.summary
    assert isinstance(summary, BronzeAnalysisSummary)
    assert summary.skipped_by_category[ChangeCategory.UNCHANGED] == 20
    # The sample is bounded; the precise cap is an implementation detail, but
    # it must be strictly less than the total so message truncation kicks in.
    sample = summary.skipped_sample_names[ChangeCategory.UNCHANGED]
    assert 1 <= len(sample) < 20
    # Message indicates how many additional skipped tables were elided.
    msg = str(exc_info.value)
    assert f"+{20 - len(sample)} more" in msg


def test_classify_runs_skip_predicate_once_per_table() -> None:
    """The DRY contract: select_actionable + build_payload must share one
    pass, so a custom predicate with side effects sees each table once
    per analyzer call — not twice."""
    cols = (BronzeColumn(name="mrid", raw_dtype="string"),)
    bronze = _bronze_snapshot(
        _bronze_table("x", columns=cols),
        _bronze_table("y", columns=cols),
    )
    cs = _change_set(
        TableChange(table_name="x", category=ChangeCategory.NEW),
        TableChange(table_name="y", category=ChangeCategory.NEW),
    )
    seen: list[str] = []

    def counting_predicate(t: BronzeTable, _c: TableChange | None) -> bool:
        seen.append(t.name)
        return False  # keep everything

    analyzer = SchemaAnalyzer(propose_fn=_stub_propose, skip_predicate=counting_predicate)
    analyzer.build_payload(system=_system(), bronze=bronze, change_set=cs)
    # One predicate invocation per bronze table — no double evaluation.
    assert seen == ["x", "y"]


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
