"""Approval-store audit report (closes H3c audit-trail + H1c approval-rate gaps).

Reads the approval audit store via the *same* factory the app uses
(:func:`make_approval_store`), so it reports on whatever backend the pipeline
actually wrote to — Delta (Databricks) or local SQLite — with no hardcoded path.

It computes the two metrics that were blocked on an empty store:

* **Audit-Trail Completeness (H3c).** Two tiers. *Structural* completeness is the
  fraction of decision records carrying every mandated provenance field (actor,
  timestamp, version, plan_id, status, plan_json) — this is 1.0 by construction
  because :class:`ApprovalRecord` makes them non-null, which is exactly the
  guarantee to report. *Rationale* completeness is the discretionary part: the
  fraction of decisions (and of rejections specifically) that carry a recorded
  reason.
* **Approval Rate (H1c).** approvals / (approvals + rejections) over all decisions,
  plus the cumulative approval rate ordered by time — the "does approval rate move
  as the corpus grows" trajectory. Drafts and changes-requested are pending, not
  decisions, so they are excluded from the rate (but counted separately).

Pure read + arithmetic; deterministic. Writes a JSON summary and prints a report.

Example
-------
    python scripts/audit/audit_report.py --out documentation/thesis/data/audit.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dbt_builder.src.ai.contracts.approval import ApprovalRecord  # noqa: E402
from dbt_builder.src.ai.store.audit_metrics import analyse  # noqa: E402


def _load_records(limit: int) -> list[ApprovalRecord]:
    """Read every stored record via the app's own store factory."""
    from dbt_builder.src.ai.settings import get_settings
    from dbt_builder.src.ai.store.approval_store import make_approval_store

    store = make_approval_store(get_settings())
    return list(store.list_recent(limit=limit))


def _print_report(a: dict) -> None:
    print("================ APPROVAL-STORE AUDIT ================")
    print(f"total records        : {a['total_records']}  by status: {a['by_status']}")
    print(f"distinct plans/actors: {a['distinct_plans']} / {a['distinct_actors']}")
    print(f"time span            : {a['time_span']}")
    print("\n-- Approval rate (H1c) --")
    print(f"decisions            : {a['decisions']}  (approved {a['approved']}, rejected {a['rejected']})")
    print(f"approval rate        : {a['approval_rate']}")
    print("\n-- Audit-trail completeness (H3c) --")
    print(f"structural (all mandated fields present): {a['audit_trail_completeness_structural']}")
    print(f"rationale coverage — all decisions      : {a['rationale_coverage_all_decisions']}")
    print(f"rationale coverage — rejections         : {a['rationale_coverage_rejections']}")
    if a["cumulative_approval_trajectory"]:
        print("\n-- Cumulative approval rate over time --")
        for row in a["cumulative_approval_trajectory"]:
            print(
                f"  #{row['n']:>2}  {row['decision']:8}  rate={row['cumulative_approval_rate']:.3f}  "
                f"{row['plan_id']}"
            )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limit", type=int, default=100_000, help="max records to read from the store")
    p.add_argument("--out", default=None, help="write the JSON summary here")
    args = p.parse_args(argv)

    records = _load_records(args.limit)
    if not records:
        print("approval store is empty (or unreachable) — nothing to report.")
        return 1
    summary = analyse(records)
    _print_report(summary)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
