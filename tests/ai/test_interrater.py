"""Inter-rater reliability helpers (gold-set triangulation)."""

from __future__ import annotations

from dbt_builder.src.ai.evaluation.gold import GoldHub, GoldModel
from dbt_builder.src.ai.evaluation.interrater import (
    gold_entity_labels,
    kappa_and_agreement,
)

# A gold with one split table (two hubs on one source) and one single-hub table.
_GOLD = GoldModel(
    system_id="s",
    hubs=(
        GoldHub(source_table="core_company", business_keys=("sys_id",), name="hub_company"),
        GoldHub(source_table="sys_user_grmember", business_keys=("user",), name="hub_user"),
        GoldHub(source_table="sys_user_grmember", business_keys=("group",), name="hub_group"),
    ),
    links=(),
    satellites=(),
)
_TABLES = ("core_company", "sys_user_grmember", "volumemetrics", "task_sla")


def test_gold_labels_hub_split_exclude():
    labels = gold_entity_labels(_GOLD, _TABLES)
    assert labels == {
        "core_company": "hub",
        "sys_user_grmember": "split",  # two hubs on one table
        "volumemetrics": "exclude",  # no hub sources it
        "task_sla": "exclude",
    }


def test_perfect_agreement_kappa_one():
    labels = gold_entity_labels(_GOLD, _TABLES)
    res = kappa_and_agreement(labels, dict(labels))
    assert res["n_items"] == 4
    assert res["raw_agreement"] == 1.0
    assert res["cohens_kappa"] == 1.0
    assert res["disagreements"] == []


def test_one_disagreement_is_reported():
    gold = gold_entity_labels(_GOLD, _TABLES)
    other = dict(gold)
    other["task_sla"] = "hub"  # rater B disagrees on one item
    res = kappa_and_agreement(gold, other)
    assert res["raw_agreement"] == 0.75
    assert res["cohens_kappa"] < 1.0
    assert res["disagreements"] == [
        {"item": "task_sla", "rater_a": "exclude", "rater_b": "hub"}
    ]


def test_requires_common_items():
    try:
        kappa_and_agreement({"a": "hub"}, {"b": "hub"})
    except ValueError as e:
        assert "common items" in str(e)
    else:
        raise AssertionError("expected ValueError on disjoint items")
