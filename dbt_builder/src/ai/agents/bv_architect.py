"""BV Architect agent (Step 4b of the v2 metadata-generator pipeline).

Splits responsibility cleanly:

* **Deterministic** PIT and Bridge proposals — driven purely by the raw-
  vault topology (which hubs have ≥2 sats, which links touch ≥2 hubs).
  No LLM, no heuristics that depend on column semantics.
* **LLM-driven** business-vault satellites — these encode business rules
  the agent cannot infer from structure. Delegated to an injected
  ``propose_bv_sats_fn`` so the module is importable without an Azure
  OpenAI client and easy to unit-test with a stub.

Why deterministic for PIT/Bridge? Because they are pure mechanical
constructs that depend only on the raw-vault topology — pulling an LLM
into them would add latency, cost, and non-determinism for zero quality
upside. The BV Architect therefore always produces *some* output (even
without an LLM bound) which is what downstream steps need.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from dbt_builder.src.ai.contracts.bv import (
    BridgeTable,
    BvProposal,
    BvSatellite,
    PitTable,
)
from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)

# Default naming conventions. Centralised so the renaming policy is one
# obvious place rather than scattered across the agent's body.
_PIT_PREFIX = "pit_"
_BRIDGE_PREFIX = "br_"
_HUB_PREFIX = "hub_"
_LINK_PREFIX = "link_"


# Public type alias — caller-supplied LLM hook for derived satellites.
ProposeBvSatsFn = Callable[[ModelingPlan, Sequence[HubDecision]], tuple[BvSatellite, ...]]


def _strip_prefix(name: str, prefix: str) -> str:
    return name[len(prefix) :] if name.startswith(prefix) else name


def _pit_name_for(hub: HubDecision) -> str:
    """Naming policy: ``hub_terminal`` -> ``pit_terminal``."""
    return _PIT_PREFIX + _strip_prefix(hub.name, _HUB_PREFIX)


def _bridge_name_for(link: LinkDecision) -> str:
    """Naming policy: ``link_terminal_node`` -> ``br_terminal_node``."""
    return _BRIDGE_PREFIX + _strip_prefix(link.name, _LINK_PREFIX)


def _satellites_per_hub(plan: ModelingPlan) -> dict[str, tuple[SatelliteDecision, ...]]:
    """Group satellites by their parent hub. Stable iteration order."""
    grouped: dict[str, list[SatelliteDecision]] = {}
    for sat in plan.satellites:
        grouped.setdefault(sat.parent_hub, []).append(sat)
    return {hub: tuple(sats) for hub, sats in grouped.items()}


class BvArchitectError(RuntimeError):
    """Raised when a caller-supplied LLM proposal violates BV invariants."""


class BvArchitect:
    """Step 4b — derive PIT/Bridge tables and (optionally) BV satellites.

    Parameters
    ----------
    propose_bv_sats_fn
        Optional callable that returns BV satellite proposals given the
        raw-vault plan and the list of hubs. When ``None``, the architect
        emits no BV satellites — keeping the deterministic PIT/Bridge
        baseline still valuable on its own.
    pit_min_satellites
        Hubs with at least this many satellites get a PIT. Default 2 —
        a single-satellite hub gets nothing because the PIT join is
        trivial.
    bridge_min_hubs
        Links with at least this many hub references get a bridge.
        Default 2.
    """

    def __init__(
        self,
        *,
        propose_bv_sats_fn: ProposeBvSatsFn | None = None,
        pit_min_satellites: int = 2,
        bridge_min_hubs: int = 2,
    ) -> None:
        if pit_min_satellites < 2:
            raise ValueError("pit_min_satellites must be >= 2 (a 1-sat PIT is trivial)")
        if bridge_min_hubs < 2:
            raise ValueError("bridge_min_hubs must be >= 2 (a single-hub link is degenerate)")
        self._propose_bv_sats_fn = propose_bv_sats_fn
        self._pit_min = pit_min_satellites
        self._bridge_min = bridge_min_hubs

    # ── deterministic ───────────────────────────────────────────────────────
    def derive_pit_tables(self, plan: ModelingPlan) -> tuple[PitTable, ...]:
        """One PIT per hub with ≥ ``pit_min_satellites`` satellites."""
        sats_by_hub = _satellites_per_hub(plan)
        out: list[PitTable] = []
        for hub in plan.hubs:
            sats = sats_by_hub.get(hub.name, ())
            if len(sats) < self._pit_min:
                continue
            out.append(
                PitTable(
                    name=_pit_name_for(hub),
                    parent_hub=hub.name,
                    satellites=tuple(s.name for s in sats),
                    rationale=(
                        f"Hub '{hub.name}' has {len(sats)} satellites; "
                        "PIT pre-joins them at the snapshot grain."
                    ),
                )
            )
        return tuple(out)

    def derive_bridge_tables(self, plan: ModelingPlan) -> tuple[BridgeTable, ...]:
        """One bridge per link with ≥ ``bridge_min_hubs`` hub references."""
        out: list[BridgeTable] = []
        for link in plan.links:
            if len(link.fk_columns) < self._bridge_min:
                continue
            out.append(
                BridgeTable(
                    name=_bridge_name_for(link),
                    parent_link=link.name,
                    hub_keys=link.fk_columns,
                    rationale=(
                        f"Link '{link.name}' joins {len(link.fk_columns)} hubs; "
                        "bridge pre-resolves the many-to-many."
                    ),
                )
            )
        return tuple(out)

    # ── LLM-backed ──────────────────────────────────────────────────────────
    def derive_bv_satellites(self, plan: ModelingPlan) -> tuple[BvSatellite, ...]:
        """Delegate to the injected propose-fn; return ``()`` when none bound."""
        if self._propose_bv_sats_fn is None:
            return ()
        proposals = self._propose_bv_sats_fn(plan, plan.hubs)
        # Belt-and-braces: refuse a proposal that names a non-existent parent hub
        # — the LLM occasionally hallucinates a hub the rest of the plan never
        # introduces, and that would crash the YAML generator with an opaque
        # error far downstream.
        hub_names = {h.name for h in plan.hubs}
        for sat in proposals:
            if sat.parent_hub not in hub_names:
                raise BvArchitectError(
                    f"BV satellite '{sat.name}' references unknown parent hub '{sat.parent_hub}'."
                )
        return tuple(proposals)

    # ── top level ───────────────────────────────────────────────────────────
    def propose(self, plan: ModelingPlan) -> BvProposal:
        """Run the full BV Architect on ``plan`` and return a typed proposal."""
        return BvProposal(
            system_id=plan.system_id,
            pit_tables=self.derive_pit_tables(plan),
            bridge_tables=self.derive_bridge_tables(plan),
            bv_satellites=self.derive_bv_satellites(plan),
        )
