"""Audit-trail + approval-rate metrics over stored approval records.

Pure functions over a list of :class:`ApprovalRecord` — no store, no I/O — so they
are unit-testable with synthetic records and reused by the reporting script
(``scripts/audit/audit_report.py``). Closes the H3c (audit-trail completeness) and
H1c (approval-rate) measurement gaps that were blocked on an empty store.
"""

from __future__ import annotations

from dbt_builder.src.ai.contracts.approval import ApprovalRecord, ApprovalStatus

# Provenance fields ApprovalRecord guarantees non-empty (the structural audit trail).
STRUCTURAL_FIELDS = ("plan_id", "version", "status", "actor", "timestamp", "plan_json")


def structurally_complete(rec: ApprovalRecord) -> bool:
    """True when every mandated provenance field on ``rec`` is present and non-empty."""
    for field in STRUCTURAL_FIELDS:
        value = getattr(rec, field, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            return False
    return True


def has_rationale(rec: ApprovalRecord) -> bool:
    """True when the record carries a non-empty comment (a recorded reason)."""
    return bool(rec.comment and rec.comment.strip())


def analyse(records: list[ApprovalRecord]) -> dict:
    """Compute audit-trail completeness + approval-rate metrics from ``records``.

    Drafts and changes-requested are pending, not terminal decisions, so they are
    counted but excluded from the approval rate. The cumulative approval trajectory
    orders terminal decisions by time — the H1c "successive runs" view.
    """
    by_status: dict[str, int] = {}
    for rec in records:
        by_status[rec.status.value] = by_status.get(rec.status.value, 0) + 1

    approved = [r for r in records if r.status is ApprovalStatus.APPROVED]
    rejected = [r for r in records if r.status is ApprovalStatus.REJECTED]
    decisions = approved + rejected
    n_dec = len(decisions)

    trajectory = []
    seen_app = 0
    for i, rec in enumerate(sorted(decisions, key=lambda r: r.timestamp), start=1):
        if rec.status is ApprovalStatus.APPROVED:
            seen_app += 1
        trajectory.append(
            {
                "n": i,
                "timestamp": rec.timestamp.isoformat(),
                "decision": rec.status.value,
                "plan_id": rec.plan_id,
                "cumulative_approval_rate": round(seen_app / i, 4),
            }
        )

    structural_complete = sum(1 for r in records if structurally_complete(r))
    rej_with_reason = sum(1 for r in rejected if has_rationale(r))
    dec_with_reason = sum(1 for r in decisions if has_rationale(r))
    plan_ids = sorted({r.plan_id for r in records})

    return {
        "total_records": len(records),
        "by_status": by_status,
        "distinct_plans": len(plan_ids),
        "distinct_actors": len(sorted({r.actor for r in records})),
        "plan_ids": plan_ids,
        "decisions": n_dec,
        "approved": len(approved),
        "rejected": len(rejected),
        "approval_rate": round(len(approved) / n_dec, 4) if n_dec else None,
        "rejection_rate": round(len(rejected) / n_dec, 4) if n_dec else None,
        "audit_trail_completeness_structural": (
            round(structural_complete / len(records), 4) if records else None
        ),
        "rationale_coverage_all_decisions": (
            round(dec_with_reason / n_dec, 4) if n_dec else None
        ),
        "rationale_coverage_rejections": (
            round(rej_with_reason / len(rejected), 4) if rejected else None
        ),
        "cumulative_approval_trajectory": trajectory,
        "time_span": (
            [
                min(r.timestamp for r in records).isoformat(),
                max(r.timestamp for r in records).isoformat(),
            ]
            if records
            else None
        ),
    }


__all__ = ["STRUCTURAL_FIELDS", "analyse", "has_rationale", "structurally_complete"]
