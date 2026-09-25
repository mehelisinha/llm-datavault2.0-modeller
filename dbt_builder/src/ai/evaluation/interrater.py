"""Inter-rater reliability of the gold sets (triangulation for the single-author gap).

The gold sets have a single author, so their reliability cannot be taken on faith.
This module reduces each gold set to a set of **categorical annotation items** — one
per source table, labelled with the core modelling decision — so agreement between
two independent labellings can be measured with Cohen's kappa (:mod:`stats`).

The item and its label space:

* item  = one source table in the discovery payload;
* label = the entity decision for that table:
    - ``hub``     — the table is one core business entity (gets a hub),
    - ``split``   — the table yields two or more business entities (>=2 hubs),
    - ``exclude`` — the table gets no hub (telemetry/measurement, a pure
                    junction/mapping table that becomes links, or an entity whose
                    identity lives in another schema).

Two labellings are compared: the **gold** labelling (derived here from the gold
file) versus a second rater — either an **independent LLM annotator** (see
``scripts/audit/interrater.py``) or the author's **re-annotation after a washout**
(intra-rater test-retest). Pure: labelling-derivation and the kappa wiring have no
I/O and are unit-tested.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from dbt_builder.src.ai.evaluation.gold import GoldModel
from dbt_builder.src.ai.evaluation.stats import cohens_kappa

ENTITY_LABELS = ("hub", "split", "exclude")


def gold_entity_labels(gold: GoldModel, all_source_tables: Sequence[str]) -> dict[str, str]:
    """Derive the per-table entity decision implied by ``gold``.

    A table appearing as the source of exactly one gold hub is ``hub``; a table
    sourcing two or more gold hubs is ``split``; a table that sources no gold hub is
    ``exclude`` (it is telemetry, a junction, or out-of-scope). ``all_source_tables``
    supplies the full item set so excluded tables are labelled, not silently dropped.
    """
    counts = Counter(h.source_table for h in gold.hubs)
    labels: dict[str, str] = {}
    for table in all_source_tables:
        n = counts.get(table, 0)
        labels[table] = "split" if n >= 2 else ("hub" if n == 1 else "exclude")
    return labels


def kappa_and_agreement(
    a: Mapping[str, str], b: Mapping[str, str]
) -> dict[str, object]:
    """Cohen's kappa + raw agreement between two per-item labellings.

    Aligns on the items both labellings cover (sorted for determinism) and returns
    the item count, raw percent agreement, kappa, the list of disagreements, and the
    label distribution of each rater — everything needed to report inter-rater
    reliability honestly, including *where* the two disagree.
    """
    items = sorted(set(a) & set(b))
    if not items:
        raise ValueError("no common items between the two labellings")
    la = [a[i] for i in items]
    lb = [b[i] for i in items]
    agree = sum(1 for x, y in zip(la, lb, strict=True) if x == y)
    disagreements = [
        {"item": i, "rater_a": a[i], "rater_b": b[i]} for i in items if a[i] != b[i]
    ]
    return {
        "n_items": len(items),
        "raw_agreement": round(agree / len(items), 4),
        "cohens_kappa": round(cohens_kappa(la, lb), 4),
        "disagreements": disagreements,
        "dist_a": dict(Counter(la)),
        "dist_b": dict(Counter(lb)),
    }


__all__ = ["ENTITY_LABELS", "gold_entity_labels", "kappa_and_agreement"]
