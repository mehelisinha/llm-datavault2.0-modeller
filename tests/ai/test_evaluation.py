"""Phase 4: DV2 conformance scorer, coverage, and blast-radius analysis."""

from __future__ import annotations

from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.evaluation import (
    IssueType,
    coverage,
    plan_blast_radius,
    score_plan,
    weighted_error_impact,
)


def _hub(name, table, bk, hk):
    return HubDecision(name=name, source_table=table, business_keys=bk, hash_key=hk)


def _sat(name, table, parent, hk, hd, payload):
    return SatelliteDecision(
        name=name, source_table=table, parent_hub=parent, hash_key=hk, hashdiff=hd, payload=payload
    )


def _clean_plan() -> ModelingPlan:
    return ModelingPlan(
        system_id="iec",
        hubs=(_hub("hub_terminal", "terminals", ("mrid",), "HK_TERMINAL"),),
        satellites=(
            _sat(
                "sat_terminal_details",
                "terminals",
                "hub_terminal",
                "HK_TERMINAL",
                "HD_TERMINAL",
                ("name",),
            ),
        ),
    )


# ── conformance ─────────────────────────────────────────────────────────────


def test_clean_plan_scores_perfectly():
    report = score_plan(_clean_plan())
    assert report.issues == ()
    assert report.score == 1.0


def test_detects_naming_surrogate_and_missing_satellite():
    plan = ModelingPlan(
        system_id="x",
        hubs=(
            _hub("customer", "cust", ("id",), "ID1"),
        ),  # bad prefix + surrogate + no HK_ + no sat
    )
    report = score_plan(plan)
    kinds = {i.type for i in report.issues}
    assert IssueType.NAMING in kinds
    assert IssueType.HASH_KEY_NAMING in kinds
    assert IssueType.SURROGATE_BUSINESS_KEY in kinds
    assert IssueType.HUB_WITHOUT_SATELLITE in kinds
    assert report.score < 1.0


def test_detects_unresolved_link_fk():
    plan = ModelingPlan(
        system_id="x",
        hubs=(
            _hub("hub_a", "a", ("ka",), "HK_A"),
            _hub("hub_b", "b", ("kb",), "HK_B"),
        ),
        links=(
            LinkDecision(
                name="link_a_b",
                source_table="a",
                hash_key="HK_A_B",
                fk_columns=("HK_A", "HK_MISSING"),
            ),
        ),
        satellites=(
            _sat("sat_a", "a", "hub_a", "HK_A", "HD_A", ("d",)),
            _sat("sat_b", "b", "hub_b", "HK_B", "HD_B", ("d",)),
        ),
    )
    report = score_plan(plan)
    assert any(i.type is IssueType.LINK_FK_UNRESOLVED for i in report.issues)


def test_detects_payload_key_leak():
    plan = ModelingPlan(
        system_id="x",
        hubs=(_hub("hub_terminal", "terminals", ("mrid",), "HK_TERMINAL"),),
        satellites=(
            _sat(
                "sat_terminal_details",
                "terminals",
                "hub_terminal",
                "HK_TERMINAL",
                "HD_TERMINAL",
                ("mrid", "name"),  # mrid is the business key
            ),
        ),
    )
    report = score_plan(plan)
    assert any(i.type is IssueType.PAYLOAD_KEY_LEAK for i in report.issues)


def test_technical_column_in_payload_flagged():
    plan = ModelingPlan(
        system_id="x",
        hubs=(_hub("hub_t", "t", ("bk",), "HK_T"),),
        satellites=(_sat("sat_t", "t", "hub_t", "HK_T", "HD_T", ("name", "load_date")),),
    )
    report = score_plan(plan, technical_columns=frozenset({"load_date"}))
    assert any(i.type is IssueType.PAYLOAD_KEY_LEAK for i in report.issues)


def test_empty_plan_flagged():
    report = score_plan(ModelingPlan(system_id="x"))
    assert any(i.type is IssueType.EMPTY_PLAN for i in report.issues)


def test_issues_by_type_covers_all_categories():
    report = score_plan(_clean_plan())
    hist = report.issues_by_type
    assert set(hist) == {t.value for t in IssueType}
    assert all(v == 0 for v in hist.values())


# ── coverage ────────────────────────────────────────────────────────────────


def test_coverage_reports_uncovered_tables():
    plan = _clean_plan()
    rep = coverage(plan, ["terminals", "orphan_table"])
    assert rep.source_tables == 2
    assert rep.covered_tables == 1
    assert rep.uncovered == ("orphan_table",)
    assert rep.coverage_ratio == 0.5


# ── blast radius ────────────────────────────────────────────────────────────


def test_blast_radius_counts_downstream_dependents():
    plan = ModelingPlan(
        system_id="x",
        hubs=(
            _hub("hub_terminal", "t", ("mrid",), "HK_TERMINAL"),
            _hub("hub_equipment", "e", ("mrid",), "HK_EQUIPMENT"),
        ),
        links=(
            LinkDecision(
                name="link_te",
                source_table="t",
                hash_key="HK_TE",
                fk_columns=("HK_TERMINAL", "HK_EQUIPMENT"),
            ),
        ),
        satellites=(
            _sat("sat_terminal_details", "t", "hub_terminal", "HK_TERMINAL", "HD_1", ("a",)),
            _sat("sat_terminal_ops", "t", "hub_terminal", "HK_TERMINAL", "HD_2", ("b",)),
        ),
    )
    radius = plan_blast_radius(plan).per_object
    # hub_terminal: 2 sats + 1 link = 3; hub_equipment: 0 sats + 1 link = 1
    assert radius["hub_terminal"] == 3
    assert radius["hub_equipment"] == 1
    assert radius["link_te"] == 0
    assert radius["sat_terminal_details"] == 0


def test_weighted_error_impact_weights_by_fanout():
    # A naming error on a high-fan-out hub costs more than the raw issue count.
    plan = ModelingPlan(
        system_id="x",
        hubs=(_hub("customer", "c", ("name",), "HK_C"),),  # NAMING issue on the hub
        satellites=(
            _sat("sat_c1", "c", "customer", "HK_C", "HD_1", ("a",)),
            _sat("sat_c2", "c", "customer", "HK_C", "HD_2", ("b",)),
        ),
    )
    report = score_plan(plan)
    # raw issues >= 1 (naming); weighted impact adds the hub's blast radius (2 sats)
    assert weighted_error_impact(plan, report) > len(report.issues)
