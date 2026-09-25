"""Significance + effect size for the experiment results (gap 4: statistical power).

Consumes the JSON written by::

    python -m dbt_builder.src.ai.evaluation experiment ... --out results.json

which contains a ``records`` list of per-(system, condition, seed) trials. For a
chosen metric this script pairs two conditions **by seed** and reports, for each
system, the paired mean difference with a bootstrap interval, a permutation
p-value (exact at these sample sizes), and Cliff's delta effect size — so a
contrast is never reported as two bare means.

Why a permutation test and not a t-test: with n=3–5 seeds a normality assumption
is indefensible; the paired permutation test is exact and assumption-free (see
:mod:`dbt_builder.src.ai.evaluation.stats`). Cliff's delta is reported alongside
so a non-significant result at low power is not confused with "no effect".

Reproducible: pure function of the input JSON and a fixed seed. No network.

Examples
--------
    # entity-F1: learning off vs on, all systems in the file, exact p-values
    python scripts/stats/significance.py --results results.json \
        --metric gold_entity_f1 --compare off,on

    # naming adherence, only ServiceNow, write a JSON next to the report
    python scripts/stats/significance.py --results results.json \
        --metric gold_naming_adherence --system SNOW_IT4IT_001 \
        --compare off,on --out significance.json
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

# Make the repo importable when run as a plain script (python scripts/...).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dbt_builder.src.ai.evaluation.stats import compare_paired  # noqa: E402

# Metrics that live on each record's ``raw``/``reviewed`` PlanMetrics block.
_KNOWN_METRICS = (
    "gold_entity_f1",
    "gold_entity_precision",
    "gold_entity_recall",
    "gold_naming_adherence",
    "gold_link_ratio",
    "correction_steps",
    "conformance_score",
    "issue_count",
    "weighted_error_impact",
)


def _seed_values(
    records: list[dict],
    *,
    system_id: str,
    condition: str,
    metric: str,
    stage: str,
) -> dict[int, float]:
    """Map ``seed -> metric value`` for one (system, condition) at a stage.

    Skips trials where the metric is null (e.g. a gold-only metric on a case with
    no gold, or a reviewed metric on a non-reviewed condition).
    """
    out: dict[int, float] = {}
    for rec in records:
        if rec["system_id"] != system_id or rec["condition"] != condition:
            continue
        block = rec.get(stage)
        if not block:
            continue
        val = block.get(metric)
        if val is not None:
            out[int(rec["seed"])] = float(val)
    return out


def _pair_by_seed(
    left: dict[int, float], right: dict[int, float]
) -> tuple[list[float], list[float], list[int]]:
    """Align two seed->value maps on their common seeds (sorted)."""
    seeds = sorted(set(left) & set(right))
    return [left[s] for s in seeds], [right[s] for s in seeds], seeds


def compare(
    records: list[dict],
    *,
    metric: str,
    condition_a: str,
    condition_b: str,
    systems: list[str] | None,
    stage: str,
    seed: int,
) -> list[dict]:
    """Run the paired comparison for every system present (or the ones given)."""
    present = systems or sorted({r["system_id"] for r in records})
    results: list[dict] = []
    for system_id in present:
        a = _seed_values(
            records, system_id=system_id, condition=condition_a, metric=metric, stage=stage
        )
        b = _seed_values(
            records, system_id=system_id, condition=condition_b, metric=metric, stage=stage
        )
        va, vb, seeds = _pair_by_seed(a, b)
        if not seeds:
            results.append(
                {
                    "system_id": system_id,
                    "metric": metric,
                    "stage": stage,
                    "condition_a": condition_a,
                    "condition_b": condition_b,
                    "note": "no common seeds with both conditions and a non-null metric",
                }
            )
            continue
        stats = compare_paired(va, vb, seed=seed)
        results.append(
            {
                "system_id": system_id,
                "metric": metric,
                "stage": stage,
                "condition_a": condition_a,
                "condition_b": condition_b,
                "seeds": seeds,
                **stats,
            }
        )
    return results


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("(no comparisons produced)")
        return
    header = (
        f"{'system':22} {'metric':22} {'A→B':>16} {'mean_a':>8} {'mean_b':>8} "
        f"{'Δ':>8} {'95% CI':>18} {'p':>7} {'δ':>7} {'effect':>11}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        ab = f"{r['condition_a']}->{r['condition_b']}"
        if "note" in r:
            print(f"{r['system_id']:22} {r['metric']:22} {ab:>16}  {r['note']}")
            continue
        ci = f"[{r['diff_ci_low']:+.3f},{r['diff_ci_high']:+.3f}]"
        print(
            f"{r['system_id']:22} {r['metric']:22} {ab:>16} "
            f"{r['mean_a']:>8.3f} {r['mean_b']:>8.3f} {r['mean_diff']:>+8.3f} "
            f"{ci:>18} {r['p_value']:>7.3f} {r['cliffs_delta']:>+7.3f} {r['effect_size']:>11}"
        )
    print(
        "\nΔ = mean(A) − mean(B); CI = 95% bootstrap on the per-seed differences; "
        "p = exact paired permutation test; δ = Cliff's delta (effect size)."
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results", required=True, help="experiment --out JSON (has a 'records' list)")
    p.add_argument("--metric", default="gold_entity_f1", help=f"one of {', '.join(_KNOWN_METRICS)}")
    p.add_argument(
        "--compare",
        default=None,
        help="two condition labels 'A,B'; if omitted, every pair of conditions is compared",
    )
    p.add_argument("--system", action="append", default=None, help="restrict to system_id (repeatable)")
    p.add_argument("--stage", default="raw", choices=("raw", "reviewed"), help="which plan to grade")
    p.add_argument("--seed", type=int, default=0, help="bootstrap/permutation seed (reproducibility)")
    p.add_argument("--out", default=None, help="write the full result rows as JSON here")
    args = p.parse_args(argv)

    payload = json.loads(Path(args.results).read_text(encoding="utf-8"))
    records = payload.get("records")
    if not records:
        print(f"no 'records' in {args.results!r}; run the experiment with --out first.")
        return 2

    conditions = sorted({r["condition"] for r in records})
    if args.compare:
        parts = [c.strip() for c in args.compare.split(",") if c.strip()]
        if len(parts) != 2:
            print("--compare needs exactly two labels, e.g. --compare off,on")
            return 2
        pairs = [(parts[0], parts[1])]
    else:
        pairs = list(combinations(conditions, 2))
        print(f"conditions in file: {conditions}\ncomparing all {len(pairs)} pair(s)\n")

    rows: list[dict] = []
    for a, b in pairs:
        rows.extend(
            compare(
                records,
                metric=args.metric,
                condition_a=a,
                condition_b=b,
                systems=args.system,
                stage=args.stage,
                seed=args.seed,
            )
        )
    _print_table(rows)

    if args.out:
        Path(args.out).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
