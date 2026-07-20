"""Deterministic heuristic classifier — the Use-Case-A rule-based baseline (Exp 5).

No network, no LLM: the classifier is pure, so these tests fully specify its
behaviour, including the failure modes that quantify where the AI layer adds value
(non-obvious keys, one-table-two-entities).
"""

from __future__ import annotations

from dbt_builder.src.ai.contracts.payloads import (
    ColumnProfile,
    DiscoveryPayload,
    SourceColumn,
    SourceSystem,
    SourceTable,
)
from dbt_builder.src.ai.evaluation.baselines import HeuristicClassifier


def _col(name, *, is_system=False, likely_key=False):
    profile = None
    if likely_key:
        profile = ColumnProfile(
            row_count=100, null_count=0, distinct_count=100,
            null_rate=0.0, cardinality_ratio=1.0, is_likely_key=True,
        )
    return SourceColumn(name=name, raw_dtype="varchar", is_system=is_system, profile=profile)


def _payload(*tables: SourceTable, system_id="SYS_1") -> DiscoveryPayload:
    return DiscoveryPayload(
        system=SourceSystem(system_id=system_id, system_name="Sys"), tables=tables
    )


def _classify(*tables: SourceTable):
    return HeuristicClassifier().propose(_payload(*tables))


# ── hubs + business keys ──────────────────────────────────────────────────────


def test_one_hub_per_table_named_after_table():
    plan = _classify(SourceTable(name="core_company", columns=(_col("sys_id"), _col("name"))))
    assert [h.name for h in plan.hubs] == ["hub_core_company"]
    assert plan.hubs[0].source_table == "core_company"


def test_profiled_likely_key_wins():
    t = SourceTable(name="t", columns=(_col("name"), _col("iso3166_3", likely_key=True)))
    plan = _classify(t)
    assert plan.hubs[0].business_keys == ("iso3166_3",)


def test_key_name_hint_used_when_no_profile():
    t = SourceTable(name="terminals", columns=(_col("name"), _col("mrid"), _col("phase")))
    plan = _classify(t)
    assert plan.hubs[0].business_keys == ("mrid",)


def test_key_suffix_used_as_fallback():
    t = SourceTable(name="t", columns=(_col("label"), _col("thing_id")))
    plan = _classify(t)
    assert plan.hubs[0].business_keys == ("thing_id",)


def test_first_column_when_no_key_signal():
    t = SourceTable(name="t", columns=(_col("alpha"), _col("beta")))
    plan = _classify(t)
    assert plan.hubs[0].business_keys == ("alpha",)


def test_system_columns_excluded_from_key_and_payload():
    t = SourceTable(
        name="t",
        columns=(_col("dl_loaded_at", is_system=True), _col("mrid"), _col("name")),
    )
    plan = _classify(t)
    assert plan.hubs[0].business_keys == ("mrid",)
    assert "dl_loaded_at" not in plan.satellites[0].payload


def test_hash_and_hashdiff_naming_conventions():
    plan = _classify(SourceTable(name="terminals", columns=(_col("mrid"), _col("name"))))
    assert plan.hubs[0].hash_key == "HK_TERMINALS"
    assert plan.satellites[0].hashdiff == "HD_TERMINALS"


# ── satellites ────────────────────────────────────────────────────────────────


def test_satellite_holds_non_key_descriptive_columns():
    t = SourceTable(name="t", columns=(_col("mrid"), _col("name"), _col("phase")))
    plan = _classify(t)
    assert plan.satellites[0].payload == ("name", "phase")
    assert plan.satellites[0].parent_hub == "hub_t"


def test_no_satellite_when_only_a_key_column():
    t = SourceTable(name="t", columns=(_col("mrid"),))
    plan = _classify(t)
    assert plan.hubs and not plan.satellites  # hub without satellite is honest output


# ── links (foreign keys) ──────────────────────────────────────────────────────


def test_fk_column_referencing_another_table_makes_a_link():
    company = SourceTable(name="company", columns=(_col("sys_id"), _col("name")))
    dept = SourceTable(name="department", columns=(_col("sys_id"), _col("company_id"), _col("name")))
    plan = HeuristicClassifier().propose(_payload(company, dept))
    assert any(ln.source_table == "department" for ln in plan.links)
    link = next(ln for ln in plan.links if ln.source_table == "department")
    assert link.fk_columns == ("HK_DEPARTMENT", "HK_COMPANY")
    # the FK column is not also dumped into the satellite payload
    dept_sat = next(s for s in plan.satellites if s.source_table == "department")
    assert "company_id" not in dept_sat.payload


def test_no_link_when_reference_target_absent():
    dept = SourceTable(name="department", columns=(_col("sys_id"), _col("company_id"), _col("name")))
    plan = _classify(dept)  # 'company' table not present
    assert plan.links == ()


def test_self_reference_is_not_a_link():
    t = SourceTable(name="company", columns=(_col("sys_id"), _col("company_id"), _col("name")))
    plan = _classify(t)
    assert plan.links == ()


# ── documented limitations (where the AI layer earns its place) ───────────────


def test_cannot_split_one_table_into_two_entities():
    # ServiceNow sys_user_grmember yields user + group in the gold, but the
    # heuristic makes exactly one hub — a deliberate, measurable limitation.
    t = SourceTable(name="sys_user_grmember", columns=(_col("user"), _col("group")))
    plan = _classify(t)
    assert len(plan.hubs) == 1


def test_deterministic_same_input_same_plan():
    t = SourceTable(name="t", columns=(_col("mrid"), _col("name"), _col("phase")))
    a = HeuristicClassifier().propose(_payload(t))
    b = HeuristicClassifier().propose(_payload(t))
    assert a == b
