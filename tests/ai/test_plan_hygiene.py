"""Deterministic plan-hygiene passes: link parsimony + business-key restoration."""

from __future__ import annotations

from dbt_builder.src.ai.agents.plan_hygiene import (
    prune_redundant_links,
    restore_business_keys,
)
from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)


def _hub(name, table, key, hk):
    return HubDecision(name=name, source_table=table, business_keys=(key,), hash_key=hk)


def _link(name, fks):
    return LinkDecision(name=name, source_table="t", hash_key=f"HK_{name}", fk_columns=fks)


def _two_hubs():
    return (_hub("hub_a", "a", "ka", "HK_A"), _hub("hub_b", "b", "kb", "HK_B"))


# ── prune_redundant_links ─────────────────────────────────────────────────────


def test_keeps_a_valid_link():
    plan = ModelingPlan(system_id="s", hubs=_two_hubs(),
                        links=(_link("l", ("HK_A", "HK_B")),))
    assert prune_redundant_links(plan) == plan  # unchanged


def test_drops_link_under_two_hubs():
    plan = ModelingPlan(system_id="s", hubs=_two_hubs(),
                        links=(_link("l", ("HK_A", "HK_A")),))  # same hub twice
    assert prune_redundant_links(plan).links == ()


def test_drops_link_with_unresolved_fk():
    plan = ModelingPlan(system_id="s", hubs=_two_hubs(),
                        links=(_link("l", ("HK_A", "HK_GHOST")),))  # HK_GHOST owned by no hub
    assert prune_redundant_links(plan).links == ()


def test_deduplicates_links_over_the_same_hub_set():
    plan = ModelingPlan(system_id="s", hubs=_two_hubs(), links=(
        _link("l1", ("HK_A", "HK_B")),
        _link("l2", ("HK_B", "HK_A")),  # same hub set, different order -> duplicate
    ))
    pruned = prune_redundant_links(plan)
    assert len(pruned.links) == 1
    assert pruned.links[0].name == "l1"  # first wins


def test_reduces_over_linking_but_keeps_valid_ones():
    plan = ModelingPlan(system_id="s",
                        hubs=(*_two_hubs(), _hub("hub_c", "c", "kc", "HK_C")),
                        links=(
                            _link("good1", ("HK_A", "HK_B")),
                            _link("good2", ("HK_B", "HK_C")),
                            _link("bad_self", ("HK_A", "HK_A")),
                            _link("bad_ghost", ("HK_A", "HK_X")),
                            _link("dup", ("HK_A", "HK_B")),
                        ))
    kept = {ln.name for ln in prune_redundant_links(plan).links}
    assert kept == {"good1", "good2"}


def test_hubs_and_satellites_untouched():
    sat = SatelliteDecision(name="sat_a", source_table="a", parent_hub="hub_a",
                            hash_key="HK_A", hashdiff="HD_A", payload=("x",))
    plan = ModelingPlan(system_id="s", hubs=_two_hubs(), satellites=(sat,),
                        links=(_link("bad", ("HK_A", "HK_A")),))
    out = prune_redundant_links(plan)
    assert out.hubs == plan.hubs and out.satellites == plan.satellites


# ── restore_business_keys ─────────────────────────────────────────────────────


def test_restores_a_rekeyed_business_key():
    original = ModelingPlan(system_id="s", hubs=(_hub("hub_company", "core_company", "name", "HK_C"),))
    reviewed = ModelingPlan(system_id="s", hubs=(_hub("hub_company", "core_company", "sys_id", "HK_C"),))
    out = restore_business_keys(reviewed, original)
    assert out.hubs[0].business_keys == ("name",)  # grounded key restored


def test_leaves_unchanged_keys_alone():
    original = ModelingPlan(system_id="s", hubs=(_hub("hub_a", "a", "ka", "HK_A"),))
    reviewed = ModelingPlan(system_id="s", hubs=(_hub("hub_a", "a", "ka", "HK_A"),))
    assert restore_business_keys(reviewed, original) == reviewed  # no-op


def test_preserves_other_reviewer_changes():
    # Reviewer re-keyed hub_a AND added a new valid hub_b — keep the new hub, fix the key.
    original = ModelingPlan(system_id="s", hubs=(_hub("hub_a", "a", "ka", "HK_A"),))
    reviewed = ModelingPlan(system_id="s", hubs=(
        _hub("hub_a", "a", "surrogate", "HK_A"), _hub("hub_b", "b", "kb", "HK_B")))
    out = restore_business_keys(reviewed, original)
    assert out.hubs[0].business_keys == ("ka",)      # restored
    assert any(h.name == "hub_b" for h in out.hubs)  # reviewer's new hub kept


def test_ignores_new_hubs_without_an_original():
    original = ModelingPlan(system_id="s", hubs=(_hub("hub_a", "a", "ka", "HK_A"),))
    reviewed = ModelingPlan(system_id="s", hubs=(
        _hub("hub_a", "a", "ka", "HK_A"), _hub("hub_new", "n", "kn", "HK_N")))
    assert restore_business_keys(reviewed, original) == reviewed  # nothing to restore
