"""Deterministic plan-hygiene passes applied after LLM generation / review.

Two evaluation findings motivate these, and both are pure ``ModelingPlan`` →
``ModelingPlan`` transforms with no LLM and no I/O:

* :func:`prune_redundant_links` — the modeller (and, to a lesser extent, the
  reviewer) **over-links**: it emits a link for many foreign-key-like columns,
  including ones that relate fewer than two hubs or reference a hash key no hub
  owns (Experiments 1, 4, 5). These links are *structurally invalid* — they are
  exactly what the conformance checks ``link_under_two_hubs`` and
  ``link_fk_unresolved`` flag — so removing them is safe and never touches a
  well-formed link. Duplicate links over the same hub set are collapsed to one.

* :func:`restore_business_keys` — the plan reviewer **re-keys hubs onto surrogate
  keys** (Experiment 4: conformance up, but entity_f1 vs the reference down because
  the business key it was grounded on was replaced). The modeller's business key is
  read from the source and is the grounded choice; this pass restores it whenever
  the reviewer changed the key of a hub it otherwise kept, preserving every *other*
  reviewer improvement.

Both are conservative: they can only make a plan *more* faithful to the source and
*more* conformant, never less, so they are safe to run by default.
"""

from __future__ import annotations

from dbt_builder.src.ai.contracts.decisions import ModelingPlan


def prune_redundant_links(plan: ModelingPlan) -> ModelingPlan:
    """Drop structurally invalid and duplicate links; keep every valid one.

    A link is kept only when it relates **at least two distinct hubs** and **every**
    foreign-key hash key it names is owned by a hub in the plan. The first link over
    a given set of hub hash keys wins; later duplicates are dropped. Hubs and
    satellites are untouched, so all cross-entity invariants still hold.
    """
    hub_hash_keys = {h.hash_key for h in plan.hubs}
    kept = []
    seen_hub_sets: set[frozenset[str]] = set()
    for link in plan.links:
        fks = frozenset(link.fk_columns)
        if len(fks) < 2:
            continue  # relates fewer than two distinct hubs
        if not fks <= hub_hash_keys:
            continue  # references a hash key no hub owns
        if fks in seen_hub_sets:
            continue  # duplicate of a link over the same hub set
        seen_hub_sets.add(fks)
        kept.append(link)

    if len(kept) == len(plan.links):
        return plan
    return ModelingPlan(
        system_id=plan.system_id,
        hubs=plan.hubs,
        links=tuple(kept),
        satellites=plan.satellites,
    )


def restore_business_keys(reviewed: ModelingPlan, original: ModelingPlan) -> ModelingPlan:
    """Restore each hub's original (grounded) business key where the reviewer changed it.

    Hubs are matched by name (the reviewer is instructed to keep names). When a
    reviewed hub shares a name with an original hub but its business key differs, the
    original key is restored; everything else the reviewer did is preserved.
    """
    original_keys = {h.name.lower(): h.business_keys for h in original.hubs}
    changed = False
    new_hubs = []
    for hub in reviewed.hubs:
        orig = original_keys.get(hub.name.lower())
        if orig is not None and orig != hub.business_keys:
            new_hubs.append(hub.model_copy(update={"business_keys": orig}))
            changed = True
        else:
            new_hubs.append(hub)
    if not changed:
        return reviewed
    return ModelingPlan(
        system_id=reviewed.system_id,
        hubs=tuple(new_hubs),
        links=reviewed.links,
        satellites=reviewed.satellites,
    )


__all__ = ["prune_redundant_links", "restore_business_keys"]
