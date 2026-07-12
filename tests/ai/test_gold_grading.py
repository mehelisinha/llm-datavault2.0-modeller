"""Phase 5: gold-set precision/recall/F1 grading."""

from __future__ import annotations

from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.evaluation import (
    GoldModel,
    grade_against_gold,
    load_gold_models,
)


def _gold() -> GoldModel:
    return GoldModel(
        system_id="t",
        hubs={"hub_user": ("user_name",), "hub_group": ("name",)},
        links=("link_user_group",),
        satellites=("sat_user_details",),
    )


def _hub(name, bk, hk):
    return HubDecision(name=name, source_table="t", business_keys=bk, hash_key=hk)


def _perfect_plan() -> ModelingPlan:
    return ModelingPlan(
        system_id="t",
        hubs=(
            _hub("hub_user", ("user_name",), "HK_USER"),
            _hub("hub_group", ("name",), "HK_GROUP"),
        ),
        links=(
            LinkDecision(
                name="link_user_group",
                source_table="t",
                hash_key="HK_UG",
                fk_columns=("HK_USER", "HK_GROUP"),
            ),
        ),
        satellites=(
            SatelliteDecision(
                name="sat_user_details",
                source_table="t",
                parent_hub="hub_user",
                hash_key="HK_USER",
                hashdiff="HD_USER",
                payload=("email",),
            ),
        ),
    )


def test_perfect_plan_scores_one():
    score = grade_against_gold(_perfect_plan(), _gold())
    assert score.hubs.f1 == 1.0
    assert score.links.f1 == 1.0
    assert score.satellites.f1 == 1.0
    assert score.business_key_accuracy == 1.0
    assert score.macro_f1 == 1.0
    assert score.core_f1 == 1.0  # mandatory tier (hubs + links)


def test_core_f1_ignores_satellites():
    # A plan that nails hubs + links but has NO satellites still scores core_f1=1.0
    # (satellites are the soft tier), while macro_f1 drops.
    plan = ModelingPlan(
        system_id="t",
        hubs=(
            _hub("hub_user", ("user_name",), "HK_USER"),
            _hub("hub_group", ("name",), "HK_GROUP"),
        ),
        links=(
            LinkDecision(
                name="link_user_group",
                source_table="t",
                hash_key="HK_UG",
                fk_columns=("HK_USER", "HK_GROUP"),
            ),
        ),
    )
    score = grade_against_gold(plan, _gold())
    assert score.core_f1 == 1.0
    assert score.satellites.f1 == 0.0
    assert score.macro_f1 < 1.0


def test_missing_and_extra_hub_lower_precision_and_recall():
    plan = ModelingPlan(
        system_id="t",
        hubs=(_hub("hub_user", ("user_name",), "HK_USER"), _hub("hub_x", ("k",), "HK_X")),
        satellites=(
            SatelliteDecision(
                name="sat_user_details",
                source_table="t",
                parent_hub="hub_user",
                hash_key="HK_USER",
                hashdiff="HD_USER",
                payload=("email",),
            ),
        ),
    )
    score = grade_against_gold(plan, _gold())
    # produced {hub_user, hub_x}, gold {hub_user, hub_group}
    assert score.hubs.true_positive == 1
    assert score.hubs.false_positive == 1  # hub_x
    assert score.hubs.false_negative == 1  # hub_group
    assert score.hubs.precision == 0.5
    assert score.hubs.recall == 0.5


def test_wrong_business_key_drops_bk_accuracy():
    plan = ModelingPlan(
        system_id="t",
        hubs=(
            _hub("hub_user", ("sys_id",), "HK_USER"),  # wrong BK (should be user_name)
            _hub("hub_group", ("name",), "HK_GROUP"),
        ),
        satellites=(
            SatelliteDecision(
                name="sat_user_details",
                source_table="t",
                parent_hub="hub_user",
                hash_key="HK_USER",
                hashdiff="HD_USER",
                payload=("email",),
            ),
        ),
    )
    score = grade_against_gold(plan, _gold())
    # both hubs matched by name, but only hub_group has the correct BK
    assert score.business_key_total == 2
    assert score.business_key_matches == 1
    assert score.business_key_accuracy == 0.5


def test_load_bundled_gold_sets():
    models = load_gold_models()
    # gold sets are keyed by their discovery system_id (not the filename)
    assert "IEC_CIM_001" in models
    assert "edh_unreg_consumption_dev" in models  # the it4it_servicenow instance
    assert models["IEC_CIM_001"].hubs["hub_terminal"] == ("mrid",)
    assert models["edh_unreg_consumption_dev"].hubs["hub_user"] == ("user",)
