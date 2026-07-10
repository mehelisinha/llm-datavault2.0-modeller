"""Command-line entry point for the evaluation / feedback-learning study.

Two commands:

* ``score``    — grade ONE plan (JSON dump of a ModelingPlan) against the DV2
                 conformance rules and, optionally, a bundled gold set. Answers
                 "is this generated model correct?" without a full run.
* ``ablation`` — run the learning OFF-vs-ON study over a directory of discovery
                 payloads, grading each against the matching gold set, and print
                 per-arm mean quality + latency. This is the dissertation table.

Examples::

    python -m dbt_builder.src.ai.evaluation score --plan plan.json --gold cim
    python -m dbt_builder.src.ai.evaluation ablation --payloads-dir ./payloads --k 3

``ablation`` builds a real modelling agent per arm (needs Azure OpenAI creds in
the environment) and toggles ``learning_examples_enabled`` between arms, so the
only difference between OFF and ON is the approved-example retrieval.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.evaluation import (
    AblationArm,
    ExperimentCase,
    evaluate_plan,
    load_gold_models,
    run_ablation,
    score_plan,
)

_ARM_OFF = "learning_off"
_ARM_ON = "learning_on"
_REPORT_COLS = (
    "n_cases",
    "conformance_score",
    "issue_count",
    "weighted_error_impact",
    "coverage_ratio",
    "gold_macro_f1",
    "gold_bk_accuracy",
    "mean_latency_s",
)


def _technical_columns() -> frozenset[str]:
    try:
        from dbt_builder.src.ai.settings import get_settings

        return get_settings().technical_payload_column_set()
    except Exception:
        return frozenset()


def _cmd_score(args: argparse.Namespace) -> int:
    plan = ModelingPlan.model_validate_json(Path(args.plan).read_text(encoding="utf-8"))
    gold = load_gold_models().get(args.gold) if args.gold else None
    if args.gold and gold is None:
        print(f"WARNING: no gold set named '{args.gold}' (have: {sorted(load_gold_models())})")
    source_tables = tuple(t for t in (args.source_tables or "").split(",") if t)

    report = score_plan(plan, technical_columns=_technical_columns())
    metrics = evaluate_plan(
        plan, source_tables=source_tables, gold=gold, technical_columns=_technical_columns()
    )

    print(f"system_id            : {plan.system_id}")
    print(
        f"objects              : {metrics.n_hubs} hubs, {metrics.n_links} links, {metrics.n_satellites} sats"
    )
    print(
        f"conformance score    : {metrics.conformance_score:.3f}  ({report.checks_passed}/{report.checks_total} checks)"
    )
    print(f"weighted error impact: {metrics.weighted_error_impact}")
    if source_tables:
        print(f"coverage             : {metrics.coverage_ratio:.3f}")
    if gold is not None:
        print(
            f"gold macro-F1        : {metrics.gold_macro_f1:.3f}  (hub {metrics.gold_hub_f1:.2f} / link {metrics.gold_link_f1:.2f} / sat {metrics.gold_sat_f1:.2f})"
        )
        print(f"business-key accuracy: {metrics.gold_bk_accuracy:.3f}")
    if report.issues:
        print(f"\nissues ({len(report.issues)}):")
        for issue in report.issues:
            where = issue.object_name or "<plan>"
            print(f"  [{issue.type.value}] {where}: {issue.message}")
    else:
        print("\nno conformance issues.")
    return 0


def _load_payloads(directory: str) -> list:
    from dbt_builder.src.ai.contracts.payloads import DiscoveryPayload

    payloads = []
    for path in sorted(Path(directory).glob("*.json")):
        payloads.append(DiscoveryPayload.model_validate_json(path.read_text(encoding="utf-8")))
    return payloads


def _cmd_ablation(args: argparse.Namespace) -> int:
    from dbt_builder.src.ai.agents.modeller import get_modelling_agent
    from dbt_builder.src.ai.settings import get_settings

    golds = load_gold_models()
    payloads = _load_payloads(args.payloads_dir)
    if not payloads:
        print(f"No *.json discovery payloads found in {args.payloads_dir!r}.")
        return 2

    cases = [
        ExperimentCase(
            system_id=p.system.system_id,
            source_tables=tuple(t.name for t in p.tables),
            gold=golds.get(p.system.system_id),
            payload=p,
        )
        for p in payloads
    ]
    matched = sum(1 for c in cases if c.gold is not None)
    print(
        f"{len(cases)} payload(s); {matched} matched to a gold set; arms: OFF vs ON(k={args.k})\n"
    )

    base = get_settings()
    agents: dict[str, object] = {}

    def agent_for(arm: AblationArm):
        if arm.label not in agents:
            cfg = base.model_copy(
                update={
                    "learning_examples_enabled": bool(arm.config["on"]),
                    "learning_examples_k": int(arm.config["k"]),
                }
            )
            agents[arm.label] = get_modelling_agent(settings=cfg, samples=args.samples)
        return agents[arm.label]

    def propose(arm: AblationArm, case: ExperimentCase) -> ModelingPlan:
        return agent_for(arm).propose(case.payload)

    arms = [
        AblationArm(_ARM_OFF, {"on": False, "k": 0}),
        AblationArm(_ARM_ON, {"on": True, "k": args.k}),
    ]
    results = run_ablation(
        cases, propose=propose, arms=arms, technical_columns=base.technical_payload_column_set()
    )
    _print_results(results)
    return 0


def _print_results(results: dict[str, dict[str, float]]) -> None:
    width = max(len(c) for c in _REPORT_COLS)
    header = "metric".ljust(width) + "".join(f"{arm:>16}" for arm in results)
    print(header)
    print("-" * len(header))
    for col in _REPORT_COLS:
        row = col.ljust(width)
        for arm in results:
            val = results[arm].get(col)
            row += "{:>16.3f}".format(val) if isinstance(val, float) else f"{'-':>16}"
        print(row)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dbt_builder.src.ai.evaluation")
    sub = parser.add_subparsers(dest="command", required=True)

    p_score = sub.add_parser("score", help="grade one ModelingPlan JSON")
    p_score.add_argument("--plan", required=True, help="path to a ModelingPlan JSON dump")
    p_score.add_argument("--gold", default=None, help="gold system_id to grade against (e.g. cim)")
    p_score.add_argument(
        "--source-tables", default=None, help="comma-separated source table names for coverage"
    )
    p_score.set_defaults(func=_cmd_score)

    p_abl = sub.add_parser("ablation", help="run the learning OFF-vs-ON study")
    p_abl.add_argument("--payloads-dir", required=True, help="dir of DiscoveryPayload *.json files")
    p_abl.add_argument("--k", type=int, default=3, help="examples retrieved in the ON arm")
    p_abl.add_argument("--samples", type=int, default=1, help="modeller votes per plan")
    p_abl.set_defaults(func=_cmd_ablation)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
