"""Approval contracts: audit-trail records for human review of plans.

Every state transition (DRAFT → APPROVED / REJECTED / CHANGES_REQUESTED, or
an EDIT) is a new immutable row in the approval store. The store is
insert-only, so reading the chain ``parent_plan_id → ... → root`` reconstructs
the full review history of any generated plan.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ApprovalStatus(str, Enum):
    """Lifecycle of a generated plan from the reviewer's perspective."""

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class ApprovalRecord(BaseModel):
    """A single row in the approval store.

    ``plan_id`` is a deterministic content hash of the generated plan
    (see :func:`dbt_builder.src.ai.utils.ids.stable_id`) so identical inputs
    yield identical IDs across runs — this is what makes the approval gate
    idempotent. ``parent_plan_id`` links edited plans back to the version they
    were derived from, forming an audit chain.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: str = Field(min_length=1)
    version: int = Field(ge=1, description="Monotonically increasing per plan_id.")
    status: ApprovalStatus
    actor: str = Field(
        min_length=1,
        description="UPN / email of the user who triggered this transition.",
    )
    timestamp: datetime
    comment: str | None = Field(default=None, max_length=4000)
    plan_json: str = Field(
        min_length=1,
        description="Serialised ModelingPlan at the time of the transition.",
    )
    validation_json: str | None = Field(
        default=None,
        description="Serialised ValidationReport that accompanied the plan.",
    )
    parent_plan_id: str | None = Field(
        default=None,
        description="plan_id of the version this record was derived from (edit chain).",
    )
