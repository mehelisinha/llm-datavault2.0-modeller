"""Deterministic, rule-based Data Vault classifier — the Use-Case-A baseline.

This is the **deterministic arm** of the three-arm baseline comparison
(Experiment 5). It maps a :class:`DiscoveryPayload` to a :class:`ModelingPlan`
using fixed, transparent rules and **no LLM** — so the evaluation can measure the
lift the AI layer provides *over rule-based automation alone*, which is exactly
what the thesis proposal's deterministic baseline was defined to isolate.

It is intentionally simple and auditable — a naïve baseline, not a competitor:

* **Hub, one per table.** Each source table becomes one hub, keyed on the best
  business-key candidate: a profiled ``is_likely_key`` column wins; otherwise a
  column whose *name* looks like a key (``mrid``, ``sys_id``, ``id``, ``<table>_id``,
  ``guid``, ``uuid``); otherwise the first non-system column. System/audit columns
  are never considered.
* **Link, per foreign key.** A non-key column whose name references *another*
  table in the payload (``<other>``, ``<other>_id``, singular/plural aware) yields
  a link between this table's hub and the referenced hub.
* **Satellite, one per hub.** The remaining descriptive columns (non-key,
  non-system, non-foreign-key) form a single ``sat_<table>_details`` payload.

By construction the rules cannot do things an LLM can — e.g. split one table into
two entities (ServiceNow ``sys_user_grmember`` → user + group), or recognise a
non-obvious semantic key (``core_country`` keyed on ``iso3166_3``). Those failures
are **the point**: they quantify where the AI layer earns its place.

Names are table-based (``hub_core_company``), like the raw modeller, so naming
adherence is graded on the same footing across arms.
"""

from __future__ import annotations

import re

from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.contracts.payloads import DiscoveryPayload, SourceColumn, SourceTable

# Column names that look like a business/surrogate key, in priority order.
_KEY_NAME_HINTS = ("mrid", "sys_id", "guid", "uuid", "uid")
_KEY_NAME_SUFFIXES = ("_id", "id", "_key", "_guid", "_uuid")


def _singular(name: str) -> str:
    """Very small English de-pluraliser for table-name matching (terminals→terminal)."""
    low = name.lower()
    if low.endswith("ies") and len(low) > 3:
        return low[:-3] + "y"
    if low.endswith("ses") and len(low) > 3:
        return low[:-2]
    if low.endswith("s") and not low.endswith("ss"):
        return low[:-1]
    return low


def _token(name: str) -> str:
    """Upper-snake token for hash-key naming (Conducting Equipment → CONDUCTING_EQUIPMENT)."""
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").upper()


def _business_columns(table: SourceTable) -> tuple[SourceColumn, ...]:
    """Columns eligible for modelling (exclude load/audit/CDC system columns)."""
    return tuple(c for c in table.columns if not c.is_system)


def _pick_business_key(table: SourceTable) -> str | None:
    """Choose one business-key column by fixed rules; None if the table is empty.

    Priority: (1) a profiled likely-key column; (2) a name that matches a key hint
    or key suffix; (3) the first non-system column. Deterministic and transparent.
    """
    cols = _business_columns(table)
    if not cols:
        return None
    for col in cols:  # (1) empirical key signal
        if col.profile is not None and col.profile.is_likely_key:
            return col.name
    for col in cols:  # (2) exact key-hint name
        if col.name.lower() in _KEY_NAME_HINTS:
            return col.name
    for col in cols:  # (2b) key-ish suffix
        if col.name.lower().endswith(_KEY_NAME_SUFFIXES):
            return col.name
    return cols[0].name  # (3) fallback: first business column


class HeuristicClassifier:
    """Rule-based DV classifier exposing the modeller's ``propose`` interface.

    Deterministic and side-effect-free: the same payload always yields the same
    plan. Drop-in for the study harness alongside the LLM modeller.
    """

    def propose(self, payload: DiscoveryPayload) -> ModelingPlan:
        tables = payload.tables
        # Map every table's singular form -> its bare name, for FK resolution.
        singular_to_table = {_singular(t.name): t.name for t in tables}

        hubs: list[HubDecision] = []
        satellites: list[SatelliteDecision] = []
        links: list[LinkDecision] = []
        hub_by_table: dict[str, HubDecision] = {}

        # ── Hubs + business keys ──────────────────────────────────────────────
        for table in tables:
            bk = _pick_business_key(table)
            if bk is None:
                continue
            tok = _token(table.name)
            hub = HubDecision(
                name=f"hub_{table.name.lower()}",
                source_table=table.name,
                business_keys=(bk,),
                hash_key=f"HK_{tok}",
                rationale="heuristic: one hub per source table",
            )
            hubs.append(hub)
            hub_by_table[table.name.lower()] = hub

        # ── Links (foreign-key columns referencing another table) + satellites ─
        used_link_names: set[str] = set()
        for table in tables:
            hub = hub_by_table.get(table.name.lower())
            if hub is None:
                continue
            bk_lower = {b.lower() for b in hub.business_keys}
            fk_cols: list[str] = []  # descriptive columns that are FKs (excluded from sat)

            for col in _business_columns(table):
                if col.name.lower() in bk_lower:
                    continue  # the table's own key is not a foreign key
                ref = _fk_target(col.name, table.name, singular_to_table)
                if ref is None:
                    continue
                ref_hub = hub_by_table.get(ref.lower())
                if ref_hub is None or ref_hub.name == hub.name:
                    continue
                link_name = f"link_{table.name.lower()}_{_singular(ref)}"
                if link_name in used_link_names:
                    continue
                used_link_names.add(link_name)
                fk_cols.append(col.name)
                links.append(
                    LinkDecision(
                        name=link_name,
                        source_table=table.name,
                        hash_key=f"HK_{_token(table.name)}_{_token(ref)}",
                        fk_columns=(hub.hash_key, ref_hub.hash_key),
                        rationale=f"heuristic: '{col.name}' references table '{ref}'",
                    )
                )

            # Satellite: remaining descriptive columns (non-key, non-FK).
            payload_cols = tuple(
                c.name
                for c in _business_columns(table)
                if c.name.lower() not in bk_lower and c.name not in fk_cols
            )
            if payload_cols:
                tok = _token(table.name)
                satellites.append(
                    SatelliteDecision(
                        name=f"sat_{table.name.lower()}_details",
                        source_table=table.name,
                        parent_hub=hub.name,
                        hash_key=hub.hash_key,
                        hashdiff=f"HD_{tok}",
                        payload=payload_cols,
                        rationale="heuristic: all non-key descriptive columns",
                    )
                )

        return ModelingPlan(
            system_id=payload.system.system_id,
            hubs=tuple(hubs),
            links=tuple(links),
            satellites=tuple(satellites),
        )


def _fk_target(
    column_name: str, own_table: str, singular_to_table: dict[str, str]
) -> str | None:
    """Return the referenced table name if ``column_name`` looks like a foreign key.

    Matches ``<other>``, ``<other>_id`` or ``<other>id`` against the singular form
    of every other table in the payload. Returns the referenced table's bare name,
    or None when the column does not reference a known table.
    """
    low = column_name.lower()
    candidates = {low}
    for suffix in ("_id", "id", "_key"):
        if low.endswith(suffix) and len(low) > len(suffix):
            candidates.add(low[: -len(suffix)])
    own_singular = _singular(own_table)
    for cand in candidates:
        singular = _singular(cand)
        if singular == own_singular:
            continue  # a self-reference is not a link to another hub
        if singular in singular_to_table:
            return singular_to_table[singular]
    return None


__all__ = ["HeuristicClassifier"]
