"""Phase 5: structural (naming-independent) gold-set grading."""

from __future__ import annotations

from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.evaluation import (
    GoldHub,
    GoldModel,
    build_from_scratch_steps,
    correction_steps,
    grade_against_gold,
    load_gold_models,
)


def _gold() -> GoldModel:
    return GoldModel(
        system_id="t",
        hubs=(
            GoldHub(source_table="core_company", business_keys=("sys_id",), name="hub_company"),
            GoldHub(source_table="sys_user_grmember", business_keys=("user",), name="hub_user"),
        ),
        links=("link_company_user",),
        satellites=("sat_company_details",),
    )


def _hub(name, table, bk):
    return HubDecision(name=name, source_table=table, business_keys=bk, hash_key="HK_X")


def test_perfect_match_entity_and_naming():
    plan = ModelingPlan(
        system_id="t",
        hubs=(
            _hub("hub_company", "core_company", ("sys_id",)),
            _hub("hub_user", "sys_user_grmember", ("user",)),
        ),
    )
    score = grade_against_gold(plan, _gold())
    assert score.entity_f1 == 1.0
    assert score.naming_adherence == 1.0


def test_table_naming_matches_entity_but_not_naming():
    # Raw modeller names: correct entities + keys, but table-based names.
    plan = ModelingPlan(
        system_id="t",
        hubs=(
            _hub("hub_core_company", "core_company", ("sys_id",)),
            _hub("hub_sys_user", "sys_user_grmember", ("user",)),
        ),
    )
    score = grade_against_gold(plan, _gold())
    assert score.entity_f1 == 1.0  # entities + keys correct (naming-independent)
    assert score.matched_entities == 2
    assert score.naming_adherence == 0.0  # neither name matches the concept name


def test_wrong_business_key_misses_the_entity():
    plan = ModelingPlan(
        system_id="t",
        hubs=(
            _hub("hub_company", "core_company", ("id",)),  # wrong key -> not the same entity
            _hub("hub_user", "sys_user_grmember", ("user",)),
        ),
    )
    score = grade_against_gold(plan, _gold())
    # company entity: model (core_company,{id}) != gold (core_company,{sys_id}) -> fp + fn
    assert score.entity.true_positive == 1  # only the user entity matched
    assert score.entity.false_positive == 1
    assert score.entity.false_negative == 1


def test_missing_and_extra_entity():
    plan = ModelingPlan(
        system_id="t",
        hubs=(
            _hub("hub_company", "core_company", ("sys_id",)),
            _hub("hub_bogus", "bogus_table", ("k",)),  # extra
        ),
    )
    score = grade_against_gold(plan, _gold())
    assert score.entity.true_positive == 1  # company
    assert score.entity.false_positive == 1  # bogus
    assert score.entity.false_negative == 1  # user missing
    assert score.entity.precision == 0.5
    assert score.entity.recall == 0.5


def test_two_entities_one_source_table():
    # sys_user_grmember -> user AND group, disambiguated by business key.
    gold = GoldModel(
        system_id="t",
        hubs=(
            GoldHub(source_table="sys_user_grmember", business_keys=("user",), name="hub_user"),
            GoldHub(source_table="sys_user_grmember", business_keys=("group",), name="hub_group"),
        ),
    )
    plan = ModelingPlan(
        system_id="t",
        hubs=(
            _hub("hub_sys_user", "sys_user_grmember", ("user",)),
            _hub("hub_sys_user_group", "sys_user_grmember", ("group",)),
        ),
    )
    score = grade_against_gold(plan, gold)
    assert score.entity_f1 == 1.0  # both entities correctly identified from one table
    assert score.naming_adherence == 0.0


def test_link_ratio_flags_over_linking():
    from dbt_builder.src.ai.contracts.decisions import LinkDecision

    plan = ModelingPlan(
        system_id="t",
        hubs=(_hub("hub_company", "core_company", ("sys_id",)),),
        links=tuple(
            LinkDecision(
                name=f"link_{i}", source_table="t", hash_key=f"HK_{i}", fk_columns=("HK_A", "HK_B")
            )
            for i in range(3)
        ),
    )
    score = grade_against_gold(plan, _gold())  # gold expects 1 link
    assert score.produced_links == 3
    assert score.expected_links == 1
    assert score.link_ratio == 3.0


# ── correction steps (H3b human-effort proxy) ────────────────────────────────


def _sat(name, table, parent):
    return SatelliteDecision(
        name=name, source_table=table, parent_hub=parent,
        hash_key="HK_X", hashdiff="HD_X", payload=("a",),
    )


def test_correction_steps_zero_for_perfect_plan():
    plan = ModelingPlan(
        system_id="t",
        hubs=(
            _hub("hub_company", "core_company", ("sys_id",)),
            _hub("hub_user", "sys_user_grmember", ("user",)),
        ),
        links=(LinkDecision(name="l", source_table="core_company", hash_key="HK_L",
                            fk_columns=("HK_A", "HK_B")),),
        satellites=(_sat("sat_company_details", "core_company", "hub_company"),),
    )
    corr = correction_steps(plan, _gold())  # gold: 2 hubs, 1 link, 1 sat
    assert corr.total == 0


def test_correction_steps_counts_add_delete_rename_and_deltas():
    # One matched-but-misnamed hub, one spurious hub, one missing hub; no links/sats.
    plan = ModelingPlan(
        system_id="t",
        hubs=(
            _hub("hub_core_company", "core_company", ("sys_id",)),  # matched, wrong name -> rename
            _hub("hub_bogus", "bogus", ("k",)),                     # spurious -> delete
        ),
    )
    corr = correction_steps(plan, _gold())
    assert corr.hub_rename == 1
    assert corr.hub_delete == 1  # bogus
    assert corr.hub_add == 1     # missing hub_user
    assert corr.link_delta == 1  # gold has 1 link, plan has 0
    assert corr.sat_delta == 1   # gold has 1 sat, plan has 0
    assert corr.total == 5


def test_mis_keyed_hub_costs_delete_plus_add():
    # Right table, wrong key -> conservative: 1 delete (spurious) + 1 add (missing).
    plan = ModelingPlan(
        system_id="t",
        hubs=(
            _hub("hub_company", "core_company", ("id",)),  # wrong key
            _hub("hub_user", "sys_user_grmember", ("user",)),
        ),
    )
    corr = correction_steps(plan, _gold())
    assert corr.hub_delete == 1  # (core_company,{id}) spurious
    assert corr.hub_add == 1     # (core_company,{sys_id}) missing


def test_build_from_scratch_steps_counts_every_gold_object():
    assert build_from_scratch_steps(_gold()) == 4  # 2 hubs + 1 link + 1 sat


def test_load_bundled_gold_sets():
    models = load_gold_models()
    assert "IEC_CIM_001" in models
    assert "SNOW_IT4IT_001" in models
    cim = models["IEC_CIM_001"]
    assert any(h.source_table == "terminals" and h.name == "hub_terminal" for h in cim.hubs)
    snow = models["SNOW_IT4IT_001"]
    # two entities on sys_user_grmember (user + group)
    grm = [h for h in snow.hubs if h.source_table == "sys_user_grmember"]
    assert {h.business_keys for h in grm} == {("user",), ("group",)}
