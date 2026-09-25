"""Tests that the v3 emitter follows the DV2 Business/Raw Vault skill rules.

Covers the skill-alignment changes: the ``as_of_dates`` section, AS_OF_DATE
(never SNAPSHOT_DATE) as the PIT snapshot column, and hub stats indexing = 4.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ai

from dbt_builder.src.ai.contracts.bv import BvProposal, PitTable  # noqa: E402
from dbt_builder.src.ai.contracts.decisions import ModelingPlan  # noqa: E402
from dbt_builder.src.ai.contracts.payloads import SourceSystem  # noqa: E402
from dbt_builder.src.ai.rendering import databricks_defaults as db  # noqa: E402
from dbt_builder.src.ai.rendering.metadata_v3_emitter import (  # noqa: E402
    build_document,
    render_v3,
)

from ._factories import hub as _hub  # noqa: E402
from ._factories import link as _link  # noqa: E402
from ._factories import plan as _plan  # noqa: E402
from ._factories import sat as _sat  # noqa: E402


def _system() -> SourceSystem:
    return SourceSystem(system_id="iec_cim", system_name="IEC CIM", source_type="delta")


def _plan_with_pit() -> tuple[ModelingPlan, BvProposal]:
    sats = (_sat("sat_terminal_details", "hub_terminal"), _sat("sat_terminal_status", "hub_terminal"))
    plan = _plan(hubs=(_hub("hub_terminal"),), satellites=sats)
    bv = BvProposal(
        system_id="iec_cim",
        pit_tables=(
            PitTable(
                name="pit_terminal",
                parent_hub="hub_terminal",
                satellites=("sat_terminal_details", "sat_terminal_status"),
            ),
        ),
    )
    return plan, bv


def test_as_of_dates_section_emitted_for_pit() -> None:
    plan, bv = _plan_with_pit()
    doc = build_document(plan, _system(), bv)
    assert "as_of_dates" in doc
    aod = doc["as_of_dates"][0]
    assert aod["name"] == "as_of_dates_iec_cim"
    assert aod["date_column"] == "AS_OF_DATE"
    assert aod["primary_hub"] == "hub_terminal"


def test_pit_references_as_of_dates_with_consistent_column() -> None:
    plan, bv = _plan_with_pit()
    doc = build_document(plan, _system(), bv)
    pit = doc["pit_tables"][0]
    assert pit["as_of_dates_table"]["name"] == "as_of_dates_iec_cim"
    assert pit["as_of_dates_table"]["date_column"] == "AS_OF_DATE"
    # PIT clustering + stats use AS_OF_DATE, never SNAPSHOT_DATE.
    assert "AS_OF_DATE" in pit["databricks_config"]["cluster_by"]


def test_no_snapshot_date_anywhere_in_rendered_yaml() -> None:
    plan, bv = _plan_with_pit()
    text = render_v3(plan, _system(), bv)
    assert "SNAPSHOT_DATE" not in text
    assert "AS_OF_DATE" in text


def test_hub_indexes_four_stats_columns() -> None:
    cfg = db.hub_config("HK_TERMINAL")
    assert cfg["table_properties"]["delta.dataSkippingNumIndexedCols"] == 4
    # Non-hub entities keep the default 8.
    assert (
        db.satellite_config("HK_TERMINAL", "HD_X")["table_properties"][
            "delta.dataSkippingNumIndexedCols"
        ]
        == 8
    )


def test_global_optimization_lists_as_of_dates_strategy() -> None:
    strategies = db.global_optimization()["incremental_strategy_defaults"]
    assert strategies["as_of_dates"] == "view"


def _two_hub_plan_with_link() -> ModelingPlan:
    hubs = (_hub("hub_terminal"), _hub("hub_node"))
    # FK columns are the hubs' hash keys — derived from the hubs, not restated.
    joined = _link("link_terminal_node", *(h.hash_key for h in hubs))
    return _plan(hubs=hubs, links=(joined,))


def test_bridge_and_fact_resolve_hubs_without_hk_unknown() -> None:
    # Regression: the BV bridge used to carry the link's fk HASH KEYS as
    # hub_keys, which the emitter could not resolve — every bridge/fact came out
    # full of HK_UNKNOWN and the fact dimensions were empty. With hub_keys now
    # resolved to hub NAMES, the rendered YAML must be free of HK_UNKNOWN and the
    # fact must list real dimensions.
    from dbt_builder.src.ai.agents import BvArchitect

    plan = _two_hub_plan_with_link()
    bv = BvArchitect().propose(plan)
    text = render_v3(plan, _system(), bv)
    assert "HK_UNKNOWN" not in text

    doc = build_document(plan, _system(), bv)
    fact = doc["fact_tables"][0]
    # Every hub the link joins is resolved to a real dimension, in fk order.
    assert fact["dimensions"] == [f"dim_{h.name.removeprefix('hub_')}" for h in plan.hubs]


def test_dims_named_by_hub_avoid_source_table_collision() -> None:
    # Two hubs derived from ONE source table (the shared "proj" table) must
    # produce two distinctly-named dimensions. Naming dims by source_table would
    # emit the same name twice (an invalid duplicate dbt model); naming by hub is
    # collision-free because hub names are unique by contract.
    shared_table = "proj"
    hubs = (
        _hub("hub_abgsl", source_table=shared_table),
        _hub("hub_pspid", source_table=shared_table),
    )
    sats = tuple(_sat(f"sat_{h.name.removeprefix('hub_')}", h.name) for h in hubs)
    plan = _plan(hubs=hubs, satellites=sats)

    names = [d["name"] for d in build_document(plan, _system(), None)["dim_tables"]]
    assert len(names) == len(set(names))  # the bug emitted the same dim twice
    # one dim per hub, each named after its hub rather than the shared table
    assert set(names) == {f"dim_{h.name.removeprefix('hub_')}" for h in hubs}


def test_staging_computes_fk_and_sat_hash_keys_in_dependency_order() -> None:
    # A link on its own table referencing hubs sourced from OTHER tables: the
    # link's staging must compute the foreign hub hash keys (so the composite
    # link hash key has its dependencies) BEFORE the composite itself. And a
    # satellite sourced from a different table than its hub must still compute
    # that hub's hash key in its own staging.
    hub_a = _hub("hub_a", source_table="ta")
    hub_b = _hub("hub_b", source_table="tb")
    joined = _link("link_a_b", hub_a.hash_key, hub_b.hash_key, source_table="tlink")
    sat_x = _sat("sat_a_extra", "hub_a", source_table="tx")
    plan = _plan(hubs=(hub_a, hub_b), links=(joined,), satellites=(sat_x,))

    staging = {s["source_table"]: s for s in build_document(plan, _system(), None)["staging"]}

    link_hashed = staging["tlink"]["hashed_columns"]
    order = list(link_hashed)
    assert hub_a.hash_key in link_hashed and hub_b.hash_key in link_hashed  # FK keys present
    assert order.index(hub_a.hash_key) < order.index(joined.hash_key)  # dependency order
    assert order.index(hub_b.hash_key) < order.index(joined.hash_key)
    assert link_hashed[joined.hash_key] == [hub_a.hash_key, hub_b.hash_key]

    sat_hashed = staging["tx"]["hashed_columns"]
    assert hub_a.hash_key in sat_hashed  # satellite's hash key computed here too
    assert sat_x.hashdiff in sat_hashed


def test_fact_dimensions_resolve_to_emitted_dims() -> None:
    # A bridge-referenced hub with no satellites must still get a dimension, so
    # the derived fact never references a missing dim model.
    from dbt_builder.src.ai.agents import BvArchitect

    hub_a = _hub("hub_a", source_table="ta")
    hub_b = _hub("hub_b", source_table="tb")  # intentionally has no satellites
    joined = _link("link_a_b", hub_a.hash_key, hub_b.hash_key, source_table="tlink")
    plan = _plan(
        hubs=(hub_a, hub_b),
        links=(joined,),
        satellites=(_sat("sat_a_details", "hub_a"),),
    )
    doc = build_document(plan, _system(), BvArchitect().propose(plan))

    dim_names = {d["name"] for d in doc.get("dim_tables", [])}
    for fact in doc.get("fact_tables", []):
        assert set(fact["dimensions"]) <= dim_names  # no dangling dimension references
    assert f"dim_{hub_b.name.removeprefix('hub_')}" in dim_names  # sat-less hub still dimensioned


def test_dangling_links_excluded_so_links_match_bridges() -> None:
    # A link whose FK references a hash key no hub owns can't be staged or
    # bridged, so it must not be emitted at all — leaving every emitted link
    # with full bridge coverage.
    from dbt_builder.src.ai.agents import BvArchitect

    hub_a = _hub("hub_a")
    hub_b = _hub("hub_b")
    good = _link("link_a_b", hub_a.hash_key, hub_b.hash_key)
    dangling = _link("link_a_ghost", hub_a.hash_key, "HK_GHOST")  # HK_GHOST: no such hub
    plan = _plan(
        hubs=(hub_a, hub_b),
        links=(good, dangling),
        satellites=(_sat("sat_a_details", "hub_a"),),
    )
    doc = build_document(plan, _system(), BvArchitect().propose(plan))

    link_names = {ln["name"] for ln in doc["links"]}
    assert "link_a_b" in link_names
    assert "link_a_ghost" not in link_names  # dangling link excluded everywhere
    assert "link_a_ghost" not in {e["parent_link"] for e in doc["eff_sats"]}
    # Every emitted link now has a bridge → section counts agree.
    assert len(doc["links"]) == len(doc.get("bridge_tables", []))
