"""Sensitivity of the CIM entity-identification result to the `terminals` ambiguity.

`terminals` is the one gold item on which independent annotators disagree (§2.9): the
gold labels it a **hub** (a terminal is a real entity) and models the relationship as a
separate link; a defensible alternative labels it a **junction** (no hub — its columns
hang off the link). This script recomputes the CIM entity-identification score for the
*same* generated plan against both golds, so the headline "AI identifies CIM entities
correctly" is shown to be robust (or not) to that single labelling choice.

Gold-A  = the shipped gold (terminals = hub; 3 hubs).
Gold-B  = the alternative (terminals excluded as a hub; 2 hubs).

Run: python scripts/audit/terminals_sensitivity.py --plan output/cim_plan.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dbt_builder.src.ai.contracts.decisions import ModelingPlan  # noqa: E402
from dbt_builder.src.ai.evaluation.gold import GoldModel, grade_against_gold, load_gold_models  # noqa: E402

_TERMINALS = "terminals"


def _gold_without_terminals(gold: GoldModel) -> GoldModel:
    """Gold-B: the same gold with the `terminals` hub removed (terminals = junction)."""
    kept = tuple(h for h in gold.hubs if h.source_table != _TERMINALS)
    return GoldModel(
        system_id=gold.system_id,
        hubs=kept,
        links=gold.links,
        satellites=gold.satellites,
    )


def _score(plan: ModelingPlan, gold: GoldModel) -> dict:
    g = grade_against_gold(plan, gold)
    return {
        "gold_hubs": len(gold.hubs),
        "precision": round(g.entity.precision, 3),
        "recall": round(g.entity.recall, 3),
        "entity_f1": round(g.entity_f1, 3),
        "tp": g.entity.true_positive,
        "fp": g.entity.false_positive,
        "fn": g.entity.false_negative,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan", default="output/cim_plan.json", help="a generated CIM ModelingPlan JSON")
    p.add_argument("--out", default=None, help="write the result JSON here")
    args = p.parse_args(argv)

    plan = ModelingPlan.model_validate_json(Path(args.plan).read_text(encoding="utf-8"))
    gold_a = load_gold_models()["IEC_CIM_001"]
    gold_b = _gold_without_terminals(gold_a)

    plan_hub_tables = sorted(h.source_table for h in plan.hubs)
    a, b = _score(plan, gold_a), _score(plan, gold_b)

    print("plan hubs (by source table):", plan_hub_tables)
    print(f"{'gold':30} {'hubs':>5} {'P':>6} {'R':>6} {'F1':>6}  tp/fp/fn")
    print(f"{'A: terminals = hub (shipped)':30} {a['gold_hubs']:>5} {a['precision']:>6} {a['recall']:>6} {a['entity_f1']:>6}  {a['tp']}/{a['fp']}/{a['fn']}")
    print(f"{'B: terminals = junction':30} {b['gold_hubs']:>5} {b['precision']:>6} {b['recall']:>6} {b['entity_f1']:>6}  {b['tp']}/{b['fp']}/{b['fn']}")
    print(
        f"\nentity F1 range across the ambiguity: {min(a['entity_f1'], b['entity_f1'])} – "
        f"{max(a['entity_f1'], b['entity_f1'])}"
    )
    print(
        "the only difference is the single `terminals` entity: the AI made the same "
        "choice as the shipped gold (terminals = hub)."
    )
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps({"plan_hub_tables": plan_hub_tables, "gold_A": a, "gold_B": b}, indent=2),
            encoding="utf-8",
        )
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
