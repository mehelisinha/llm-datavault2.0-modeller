"""Tests for the BV-sat proposer factory + its wiring into the BV Architect.

The proposer is the optional third LLM touchpoint; these tests confirm it stays
OFF by default (so the pipeline's LLM usage is unchanged) and that the service
wires a deterministic-only architect when it is disabled — without needing any
Azure credentials.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ai

from dbt_builder.src.ai.agents import BvArchitect  # noqa: E402
from dbt_builder.src.ai.agents.bv_sat_proposer import get_bv_sat_proposer  # noqa: E402
from dbt_builder.src.ai.settings import AISettings  # noqa: E402


def test_factory_returns_none_when_disabled() -> None:
    cfg = AISettings(bv_sats_enabled=False)  # type: ignore[call-arg]
    assert get_bv_sat_proposer(settings=cfg) is None


def test_factory_returns_none_when_enabled_but_no_deployment() -> None:
    # Enabled but neither a BV-sat deployment nor a modeller deployment to fall
    # back to → safely skipped (None), never a crash.
    cfg = AISettings(  # type: ignore[call-arg]
        bv_sats_enabled=True,
        bv_sat_chat_deployment="",
        modeller_chat_deployment="",
    )
    assert get_bv_sat_proposer(settings=cfg) is None


def test_default_architect_is_deterministic_when_proposer_disabled() -> None:
    # With the proposer off, the service must wire a plain (deterministic-only)
    # BV Architect — no BV satellites, no LLM dependency.
    from dbt_builder.src.ai.service import _try_build_default_bv_architect

    architect = _try_build_default_bv_architect()
    assert isinstance(architect, BvArchitect)
    # A deterministic architect proposes no BV satellites for any plan.
    from ._factories import hub, plan, sat

    sample = plan(
        hubs=(hub("hub_terminal"),),
        satellites=(
            sat("sat_terminal_details", "hub_terminal"),
            sat("sat_terminal_status", "hub_terminal"),
        ),
    )
    assert architect.propose(sample).bv_satellites == ()
