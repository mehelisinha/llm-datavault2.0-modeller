"""Audit-trail + approval-rate metrics (H3c / H1c), computed on synthetic records."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dbt_builder.src.ai.contracts.approval import ApprovalRecord, ApprovalStatus
from dbt_builder.src.ai.store.audit_metrics import (
    analyse,
    has_rationale,
    structurally_complete,
)

_T0 = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


def _rec(i: int, status: ApprovalStatus, *, comment: str | None = None) -> ApprovalRecord:
    return ApprovalRecord(
        plan_id=f"sys_{i % 2}",
        version=i,
        status=status,
        actor="dev@local",
        timestamp=_T0 + timedelta(minutes=i),
        comment=comment,
        plan_json="{}",
    )


def test_structural_completeness_and_rationale_helpers():
    r = _rec(1, ApprovalStatus.APPROVED)
    assert structurally_complete(r) is True  # schema guarantees the mandated fields
    assert has_rationale(r) is False
    assert has_rationale(_rec(2, ApprovalStatus.REJECTED, comment="not grounded")) is True


def test_approval_rate_excludes_pending_states():
    records = [
        _rec(1, ApprovalStatus.APPROVED),
        _rec(2, ApprovalStatus.APPROVED),
        _rec(3, ApprovalStatus.REJECTED, comment="fabricated table"),
        _rec(4, ApprovalStatus.DRAFT),  # pending — not a decision
        _rec(5, ApprovalStatus.CHANGES_REQUESTED),  # pending — not a decision
    ]
    a = analyse(records)
    assert a["decisions"] == 3  # 2 approved + 1 rejected; drafts/changes excluded
    assert a["approved"] == 2 and a["rejected"] == 1
    assert a["approval_rate"] == 0.6667  # 2/3, rounded to 4 dp
    assert a["audit_trail_completeness_structural"] == 1.0
    # Only the rejection carried a reason.
    assert a["rationale_coverage_rejections"] == 1.0


def test_cumulative_trajectory_is_time_ordered():
    # Two early rejections then two approvals → rate climbs 0, 0, 0.33, 0.5.
    records = [
        _rec(4, ApprovalStatus.APPROVED),
        _rec(1, ApprovalStatus.REJECTED, comment="a"),
        _rec(3, ApprovalStatus.APPROVED),
        _rec(2, ApprovalStatus.REJECTED, comment="b"),
    ]
    traj = analyse(records)["cumulative_approval_trajectory"]
    assert [row["cumulative_approval_rate"] for row in traj] == [0.0, 0.0, 0.3333, 0.5]


def test_empty_store_yields_none_rates():
    a = analyse([])
    assert a["decisions"] == 0
    assert a["approval_rate"] is None
    assert a["audit_trail_completeness_structural"] is None
