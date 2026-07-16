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
    StageRecord,
    evaluate_plan,
    grade_against_gold,
    load_gold_models,
    parse_condition,
    run_ablation,
    run_study,
    score_plan,
    summarise,
)

_ARM_OFF = "learning_off"
_ARM_ON = "learning_on"
_REPORT_COLS = (
    "n_cases",
    "conformance_score",
    "issue_count",
    "weighted_error_impact",
    "coverage_ratio",
    "gold_entity_f1",
    "gold_naming_adherence",
    "gold_link_ratio",
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
        g = grade_against_gold(plan, gold)
        print("\ngold grading (structural — naming-independent):")
        print(
            f"  entity id (source_table + business key): "
            f"P/R/F1 = {g.entity.precision:.2f} / {g.entity.recall:.2f} / {g.entity_f1:.2f}"
            f"   (tp={g.entity.true_positive} fp={g.entity.false_positive} fn={g.entity.false_negative})"
        )
        print(
            f"  naming adherence (concept names)       : {g.naming_adherence:.2f}"
            f"   ({g.naming_matches}/{g.matched_entities} matched entities use the shop name)"
        )
        print(
            f"  links produced/expected                : {g.produced_links}/{g.expected_links}"
            f"   (ratio {g.link_ratio:.2f}; >1 = over-linking)"
        )
        print(
            f"  satellites produced/expected           : {g.produced_satellites}/{g.expected_satellites}"
        )
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


def _cmd_approve(args: argparse.Namespace) -> int:
    """Approve a previously-generated plan JSON (the EXACT plan you scored).

    Use this for the see-precision-THEN-approve workflow: `generate --out plan.json`
    to review the scorecard, then `approve --plan plan.json --payload disc.yaml` to
    store that same plan (no regeneration, so the score you saw is what you store).
    """
    from dbt_builder.src.ai.discovery.schema_discovery import discover_from_yaml

    plan = ModelingPlan.model_validate_json(Path(args.plan).read_text(encoding="utf-8"))
    payload = discover_from_yaml(args.payload)
    return _approve_plan(plan, payload, actor=args.actor)


def _cmd_reject(args: argparse.Namespace) -> int:
    """Record a REJECT decision for a generated plan (audit only, no corpus write).

    Rejecting is human feedback too: it does NOT add the plan to the learning
    corpus, but it IS logged in the approval audit trail — so you can compute the
    approval rate (approved / (approved + rejected)) over your experiment runs.
    """
    from dbt_builder.src.ai.discovery.schema_discovery import discover_from_yaml
    from dbt_builder.src.ai.rendering.metadata_v3_emitter import render_v3
    from dbt_builder.src.ai.service import DwaService

    plan = ModelingPlan.model_validate_json(Path(args.plan).read_text(encoding="utf-8"))
    payload = discover_from_yaml(args.payload)
    service = DwaService()
    bv = service.architect_bv(plan)
    rendered = render_v3(plan, payload.system, bv)
    validation = service.validate(plan=plan, rendered_yaml=rendered, bv=bv)
    service.submit_for_review(
        plan=plan, rendered_yaml=rendered, validation=validation, actor=args.actor
    )
    record = service.reject(plan_id=validation.plan_id, actor=args.actor, comment=args.comment)
    print(
        f"[REJECTED] plan_id={record.plan_id} by {args.actor} — logged in the approval "
        "audit trail; NOT added to the learning corpus."
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


def _print_record(rec: StageRecord) -> None:
    """One-line live progress for a finished trial (raw -> reviewed when reviewed)."""
    raw = rec.raw
    line = (
        f"[{rec.system_id:14} {rec.condition:10} s={rec.seed}] "
        f"ef1={raw.gold_entity_f1:.2f} nam={raw.gold_naming_adherence:.2f} "
        f"conf={raw.conformance_score:.2f} iss={raw.issue_count} "
        f"wimpact={raw.weighted_error_impact} lr={raw.gold_link_ratio:.2f} "
        f"| model {rec.t_model_s:.0f}s"
    )
    if rec.reviewed is not None:
        rv = rec.reviewed
        line += (
            f"  ->REV ef1={rv.gold_entity_f1:.2f} nam={rv.gold_naming_adherence:.2f} "
            f"conf={rv.conformance_score:.2f} iss={rv.issue_count} "
            f"wimpact={rv.weighted_error_impact} lr={rv.gold_link_ratio:.2f} "
            f"(review {rec.t_review_s:.0f}s)"
        )
    print(line, flush=True)


def _cmd_experiment(args: argparse.Namespace) -> int:
    """Run a declarative study: systems × conditions × seeds, raw (+reviewed).

    Subsumes every experiment (ablation, learning curve, cross-domain control,
    end-to-end reviewer + taxonomy shift). Nothing is hardcoded: systems are gold
    ``system_id``s (payload path read from the gold file) and conditions are
    parsed specs like ``off``, ``on:k=10``, ``loo:k=10,exclude=a+b``, ``e2e:k=10,review=1``.
    """
    from dbt_builder.src.ai.settings import get_settings

    systems = [s for s in ",".join(args.system).split(",") if s]
    conditions = [parse_condition(c) for c in args.condition]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    print(
        f"systems={systems}  conditions={[c.label for c in conditions]}  "
        f"seeds={seeds}  samples={args.samples}\n"
    )
    records = run_study(
        systems=systems,
        conditions=conditions,
        seeds=seeds,
        settings=get_settings(),
        samples=args.samples,
        on_record=_print_record,
    )
    _print_study_summary(summarise(records))
    if args.out:
        import json

        payload = {
            "records": [r.model_dump() for r in records],
            "summary": _summary_to_jsonable(summarise(records)),
        }
        Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nresults written to {args.out}")
    return 0


def _summary_to_jsonable(summary: dict) -> dict:
    """Flatten the summarise() output (dataclasses/models) into plain JSON."""
    out: dict = {}
    for key, cell in summary.items():
        entry: dict = {}
        for stage in ("raw", "reviewed"):
            s = cell.get(stage)
            entry[stage] = (
                None
                if s is None
                else {
                    "means": s.means,
                    "issues_by_type": s.issues_by_type,
                    "naming_per_seed": list(s.naming_per_seed),
                }
            )
        shift = cell.get("shift")
        entry["shift"] = None if shift is None else shift.model_dump()
        out[key] = entry
    return out


def _print_study_summary(summary: dict) -> None:
    """Print per-(system/condition) raw->reviewed means + error-taxonomy shift."""
    print("\n=== STUDY SUMMARY (means over seeds) ===")
    for key, cell in summary.items():
        raw = cell["raw"]
        rev = cell.get("reviewed")
        print(f"\n{key}:")
        for f in ("gold_entity_f1", "gold_naming_adherence", "conformance_score",
                  "issue_count", "weighted_error_impact", "gold_link_ratio"):
            rv = "" if rev is None else f" -> {rev.means.get(f)}"
            print(f"  {f:22} {raw.means.get(f)}{rv}")
        print(f"  taxonomy raw     : {raw.issues_by_type or '{}'}")
        if rev is not None:
            print(f"  taxonomy reviewed: {rev.issues_by_type or '{}'}")
            shift = cell["shift"]
            print(f"  resolved         : {shift.resolved or '{}'}")
            print(f"  introduced       : {shift.introduced or '{}'}")
            print(f"  net_resolved     : {shift.net_resolved}")


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

    p_app = sub.add_parser("approve", help="approve a saved plan JSON (the exact plan you scored)")
    p_app.add_argument(
        "--plan", required=True, help="path to a ModelingPlan JSON (from generate --out)"
    )
    p_app.add_argument("--payload", required=True, help="the discovery YAML used to generate it")
    p_app.add_argument("--actor", default="evaluator@local", help="approver identity")
    p_app.set_defaults(func=_cmd_approve)

    p_rej = sub.add_parser("reject", help="record a REJECT for a saved plan (audit only)")
    p_rej.add_argument(
        "--plan", required=True, help="path to a ModelingPlan JSON (from generate --out)"
    )
    p_rej.add_argument("--payload", required=True, help="the discovery YAML used to generate it")
    p_rej.add_argument("--actor", default="evaluator@local", help="reviewer identity")
    p_rej.add_argument("--comment", default="rejected via CLI", help="reason for rejection")
    p_rej.set_defaults(func=_cmd_reject)

    p_abl = sub.add_parser("ablation", help="run the learning OFF-vs-ON study")
    p_abl.add_argument("--payloads-dir", required=True, help="dir of DiscoveryPayload *.json files")
    p_abl.add_argument("--k", type=int, default=3, help="examples retrieved in the ON arm")
    p_abl.add_argument("--samples", type=int, default=1, help="modeller votes per plan")
    p_abl.set_defaults(func=_cmd_ablation)

    p_exp = sub.add_parser(
        "experiment",
        help="run a declarative study: systems × conditions × seeds (raw + optional reviewer)",
    )
    p_exp.add_argument(
        "--system",
        action="append",
        required=True,
        help="gold system_id (repeatable or comma-separated), e.g. SNOW_IT4IT_001",
    )
    p_exp.add_argument(
        "--condition",
        action="append",
        required=True,
        help="condition spec (repeatable): off | on:k=10 | loo:k=10,exclude=a+b | e2e:k=10,review=1",
    )
    p_exp.add_argument("--seeds", default="42", help="comma-separated seeds, e.g. 42,43")
    p_exp.add_argument("--samples", type=int, default=1, help="modeller votes per plan")
    p_exp.add_argument("--out", default=None, help="write full records + summary JSON here")
    p_exp.set_defaults(func=_cmd_experiment)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
