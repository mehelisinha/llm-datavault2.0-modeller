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
    "gold_core_f1",
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


def _print_scorecard(plan, *, source_tables, gold, technical) -> None:
    """Print the conformance + gold scorecard for one plan (shared by score/generate)."""
    report = score_plan(plan, technical_columns=technical)
    metrics = evaluate_plan(
        plan, source_tables=source_tables, gold=gold, technical_columns=technical
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
            f"gold core-F1 (mand.) : {metrics.gold_core_f1:.3f}  (hub {metrics.gold_hub_f1:.2f} / link {metrics.gold_link_f1:.2f})"
        )
        print(
            f"gold macro-F1 (+sat) : {metrics.gold_macro_f1:.3f}  (sat {metrics.gold_sat_f1:.2f} — soft tier)"
        )
        print(f"business-key accuracy: {metrics.gold_bk_accuracy:.3f}")
    if report.issues:
        print(f"\nissues ({len(report.issues)}):")
        for issue in report.issues:
            where = issue.object_name or "<plan>"
            print(f"  [{issue.type.value}] {where}: {issue.message}")
    else:
        print("\nno conformance issues.")


def _cmd_score(args: argparse.Namespace) -> int:
    plan = ModelingPlan.model_validate_json(Path(args.plan).read_text(encoding="utf-8"))
    gold = load_gold_models().get(args.gold) if args.gold else None
    if args.gold and gold is None:
        print(f"WARNING: no gold set named '{args.gold}' (have: {sorted(load_gold_models())})")
    source_tables = tuple(t for t in (args.source_tables or "").split(",") if t)
    _print_scorecard(plan, source_tables=source_tables, gold=gold, technical=_technical_columns())
    return 0


def _approve_plan(plan, payload, *, actor: str) -> int:
    """Run the real approval flow so the SCORED plan lands in Databricks + corpus.

    Renders v3 YAML, runs the validation gate, submits a DRAFT, then approves.
    Approval writes yaml_versions + approvals + rv_examples (the learning corpus),
    so the exact plan you evaluated is what future runs learn from.
    """
    from dbt_builder.src.ai.rendering.metadata_v3_emitter import render_v3
    from dbt_builder.src.ai.service import DwaService

    service = DwaService()
    bv = service.architect_bv(plan)
    rendered = render_v3(plan, payload.system, bv)
    validation = service.validate(plan=plan, rendered_yaml=rendered, bv=bv)
    if not validation.passed:
        print(
            f"\n[BLOCKED] validation has {validation.summary.errors} ERROR-severity issue(s) — "
            "approval gate refuses. Fix the plan and re-run."
        )
        return 1
    service.submit_for_review(plan=plan, rendered_yaml=rendered, validation=validation, actor=actor)
    record = service.approve(plan_id=validation.plan_id, actor=actor)
    print(
        f"\n[APPROVED] plan_id={record.plan_id} v{record.version} by {actor} — "
        "stored to yaml_versions + approvals + rv_examples (corpus)."
    )
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    from dbt_builder.src.ai.agents.modeller import get_modelling_agent
    from dbt_builder.src.ai.discovery.schema_discovery import discover_from_yaml
    from dbt_builder.src.ai.settings import get_settings

    payload = discover_from_yaml(args.payload)
    cfg = get_settings()
    if args.no_learning:
        cfg = cfg.model_copy(update={"learning_examples_enabled": False})
    learning = (
        "off" if args.no_learning else ("on" if cfg.learning_examples_enabled else "off (settings)")
    )
    print(
        f"generating for system_id={payload.system.system_id} "
        f"({len(payload.tables)} tables, learning={learning})...\n"
    )

    agent = get_modelling_agent(settings=cfg, samples=args.samples)
    plan = agent.propose(payload)

    gold = load_gold_models().get(args.gold or payload.system.system_id)
    source_tables = tuple(t.name for t in payload.tables)
    _print_scorecard(
        plan, source_tables=source_tables, gold=gold, technical=cfg.technical_payload_column_set()
    )

    if args.out:
        Path(args.out).write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        print(f"\nplan written to {args.out}")

    if args.approve:
        return _approve_plan(plan, payload, actor=args.actor)
    else:
        print("\n(dry run — pass --approve to store this plan in the corpus)")
    return 0


def _load_payloads(directory: str) -> list:
    """Load DiscoveryPayloads from a directory.

    Accepts both formats a user can produce without the web app:

    * ``*.yaml`` / ``*.yml`` — the offline discovery shape (``system`` + ``tables``)
      read by :func:`discover_from_yaml` (e.g. ``poc/metadata/iec_cim_discovery.yaml``).
    * ``*.json`` — a raw ``DiscoveryPayload`` dump (e.g. exported from a run).

    The web-app pipeline builds the payload internally and does not export it, so
    the discovery YAML is the canonical file artifact for the study.
    """
    from dbt_builder.src.ai.contracts.payloads import DiscoveryPayload
    from dbt_builder.src.ai.discovery.schema_discovery import discover_from_yaml

    base = Path(directory)
    payloads = []
    for path in sorted(base.glob("*.yaml")) + sorted(base.glob("*.yml")):
        payloads.append(discover_from_yaml(path))
    for path in sorted(base.glob("*.json")):
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

    p_gen = sub.add_parser(
        "generate", help="generate a plan from a discovery YAML, score it, optionally approve"
    )
    p_gen.add_argument("--payload", required=True, help="discovery YAML (system + tables)")
    p_gen.add_argument("--gold", default=None, help="gold system_id (defaults to the payload's)")
    p_gen.add_argument("--out", default=None, help="write the generated ModelingPlan JSON here")
    p_gen.add_argument("--samples", type=int, default=1, help="modeller votes per plan")
    p_gen.add_argument("--no-learning", action="store_true", help="force learning OFF for this run")
    p_gen.add_argument(
        "--approve", action="store_true", help="approve + store the plan (corpus write)"
    )
    p_gen.add_argument(
        "--actor", default="evaluator@local", help="approver identity (with --approve)"
    )
    p_gen.set_defaults(func=_cmd_generate)

    p_abl = sub.add_parser("ablation", help="run the learning OFF-vs-ON study")
    p_abl.add_argument("--payloads-dir", required=True, help="dir of DiscoveryPayload *.json files")
    p_abl.add_argument("--k", type=int, default=3, help="examples retrieved in the ON arm")
    p_abl.add_argument("--samples", type=int, default=1, help="modeller votes per plan")
    p_abl.set_defaults(func=_cmd_ablation)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
