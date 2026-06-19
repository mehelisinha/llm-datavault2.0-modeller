"""Tests for the BV Architect agent (Phase B / Step 4b)."""

from __future__ import annotations

import pytest

from dbt_builder.src.ai.agents import BvArchitect
from dbt_builder.src.ai.contracts.bv import (
    BridgeTable,
    BvProposal,
    BvSatellite,
    PitTable,
)
from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    ModelingPlan,
)

from ._factories import hub as _hub
from ._factories import link as _link
from ._factories import plan as _plan_factory
from ._factories import sat as _sat


def _plan(*, hubs=(), sats=(), links=()) -> ModelingPlan:
    """Thin adapter to the shared factory (keeps the ``sats=`` call style)."""
    return _plan_factory(hubs=hubs, satellites=sats, links=links)


# ── deterministic PIT ───────────────────────────────────────────────────────


def test_pit_emitted_for_hub_with_two_satellites() -> None:
    hub = _hub("hub_terminal")
    plan = _plan(
        hubs=(hub,),
        sats=(
            _sat("sat_terminal_details", "hub_terminal"),
            _sat("sat_terminal_status", "hub_terminal"),
        ),
    )
    proposal = BvArchitect().propose(plan)
    assert len(proposal.pit_tables) == 1
    pit = proposal.pit_tables[0]
    assert pit.name == "pit_terminal"
    assert pit.parent_hub == "hub_terminal"
    assert pit.satellites == ("sat_terminal_details", "sat_terminal_status")


def test_no_pit_for_single_satellite_hub() -> None:
    hub = _hub("hub_terminal")
    plan = _plan(hubs=(hub,), sats=(_sat("sat_terminal_details", "hub_terminal"),))
    assert BvArchitect().propose(plan).pit_tables == ()


def test_pit_threshold_is_configurable() -> None:
    hub = _hub("hub_terminal")
    plan = _plan(
        hubs=(hub,),
        sats=(
            _sat("sat_a", "hub_terminal"),
            _sat("sat_b", "hub_terminal"),
            _sat("sat_c", "hub_terminal"),
        ),
    )
    arch = BvArchitect(pit_min_satellites=4)
    assert arch.propose(plan).pit_tables == ()
    arch_low = BvArchitect(pit_min_satellites=3)
    assert len(arch_low.propose(plan).pit_tables) == 1


def test_pit_threshold_must_be_at_least_two() -> None:
    with pytest.raises(ValueError):
        BvArchitect(pit_min_satellites=1)


# ── deterministic Bridge ───────────────────────────────────────────────────


def test_bridge_emitted_for_two_hub_link() -> None:
    plan = _plan(
        hubs=(_hub("hub_terminal"), _hub("hub_node")),
        links=(_link("link_terminal_node", "HK_TERMINAL", "HK_NODE"),),
    )
    proposal = BvArchitect().propose(plan)
    assert len(proposal.bridge_tables) == 1
    br = proposal.bridge_tables[0]
    assert br.name == "br_terminal_node"
    # hub_keys are resolved from the link's fk hash keys to hub NAMES so the
    # emitter can look them up (otherwise it falls back to HK_UNKNOWN).
    assert br.hub_keys == ("hub_terminal", "hub_node")


def test_bridge_skipped_when_fks_resolve_to_too_few_hubs() -> None:
    # A link whose fk hash keys don't match any hub in the plan is a dangling
    # reference: the bridge would only emit HK_UNKNOWN, so it must be skipped.
    plan = _plan(
        hubs=(_hub("hub_terminal"),),
        links=(_link("link_terminal_ghost", "HK_TERMINAL", "HK_GHOST"),),
    )
    assert BvArchitect().propose(plan).bridge_tables == ()


def test_bridge_threshold_must_be_at_least_two() -> None:
    with pytest.raises(ValueError):
        BvArchitect(bridge_min_hubs=1)


# ── LLM-backed BV satellites ───────────────────────────────────────────────


def test_no_bv_sats_when_no_propose_fn() -> None:
    plan = _plan(hubs=(_hub("hub_terminal"),))
    assert BvArchitect().propose(plan).bv_satellites == ()


def test_bv_sat_propose_fn_is_called_with_plan_and_hubs() -> None:
    plan = _plan(hubs=(_hub("hub_terminal"),))
    captured: list[tuple[ModelingPlan, tuple[HubDecision, ...]]] = []

    def fake(p: ModelingPlan, hubs):
        captured.append((p, tuple(hubs)))
        return (
            BvSatellite(
                name="bv_sat_terminal_score",
                parent_hub="hub_terminal",
                source_models=("hub_terminal", "sat_terminal_details"),
                computed_columns=("risk_score",),
                rationale="domain rule",
            ),
        )

    proposal = BvArchitect(propose_bv_sats_fn=fake).propose(plan)
    assert len(captured) == 1
    assert captured[0][0] is plan
    assert proposal.bv_satellites[0].name == "bv_sat_terminal_score"


def test_bv_sat_with_unknown_parent_hub_is_dropped_not_fatal() -> None:
    # A BV satellite naming a non-existent parent hub is dropped (logged), not
    # raised — the optional BV layer must never fail the pipeline.
    plan = _plan(hubs=(_hub("hub_terminal"),))

    def fake(p: ModelingPlan, hubs):
        return (
            BvSatellite(
                name="bv_sat_ghost",
                parent_hub="hub_does_not_exist",
                source_models=("x",),
                computed_columns=("y",),
            ),
        )

    proposal = BvArchitect(propose_bv_sats_fn=fake).propose(plan)
    assert proposal.bv_satellites == ()


def test_bv_sat_proposer_exception_does_not_break_proposal() -> None:
    # If the proposer itself raises (e.g. an LLM/parse failure), the BV
    # Architect still returns a valid proposal with no BV satellites.
    plan = _plan(hubs=(_hub("hub_terminal"),))

    def boom(p: ModelingPlan, hubs):
        raise RuntimeError("proposer exploded")

    proposal = BvArchitect(propose_bv_sats_fn=boom).propose(plan)
    assert proposal.bv_satellites == ()


# ── proposal invariants ────────────────────────────────────────────────────


def test_proposal_rejects_duplicate_object_names() -> None:
    with pytest.raises(ValueError):
        BvProposal(
            system_id="x",
            pit_tables=(
                PitTable(
                    name="pit_clash",
                    parent_hub="hub_a",
                    satellites=("sat_x",),
                ),
            ),
            bridge_tables=(
                BridgeTable(
                    name="pit_clash",
                    parent_link="link_a",
                    hub_keys=("HK_A", "HK_B"),
                ),
            ),
        )


def test_propose_is_deterministic_for_same_plan() -> None:
    hub = _hub("hub_terminal")
    plan = _plan(
        hubs=(hub,),
        sats=(
            _sat("sat_terminal_details", "hub_terminal"),
            _sat("sat_terminal_status", "hub_terminal"),
        ),
    )
    arch = BvArchitect()
    a = arch.propose(plan)
    b = arch.propose(plan)
    assert a == b
