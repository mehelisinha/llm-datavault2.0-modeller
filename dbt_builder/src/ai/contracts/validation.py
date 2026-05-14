"""Validation contracts used by Step 6 (Validator) and the UI Review page.

A ``ValidationReport`` is the single artefact the UI displays in its
"Validation passed / N issues" banner and the audit store keeps as proof
of what was checked at approval time. Severity drives the approval gate:
any ERROR blocks approval; WARNINGs do not.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    """Issue severity. ERROR blocks approval; WARNING/INFO do not."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue(BaseModel):
    """A single issue produced by one of the validator's deterministic checks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(
        min_length=1,
        description=(
            "Stable machine-readable code (e.g. 'YAML_SYNTAX', 'ORPHAN_SAT', "
            "'APPEND_ONLY_ON_EFF_SAT'). Used by the UI to look up help text."
        ),
    )
    severity: Severity
    message: str = Field(min_length=1)
    location: str | None = Field(
        default=None,
        description=(
            "Free-text pointer to the offending node "
            "(e.g. 'satellites[3].parent_hub' or 'system_metadata.yml:L142')."
        ),
    )
    suggestion: str | None = Field(
        default=None,
        description="Optional remediation hint shown in the UI.",
    )


class CheckSummary(BaseModel):
    """Aggregate counts per severity, used by the UI banner."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    errors: int = Field(default=0, ge=0)
    warnings: int = Field(default=0, ge=0)
    infos: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        return self.errors + self.warnings + self.infos


class ValidationReport(BaseModel):
    """Complete output of Step 6 — Validator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: str = Field(min_length=1)
    computed_at: datetime
    issues: tuple[ValidationIssue, ...] = ()
    summary: CheckSummary
    checks_run: tuple[str, ...] = Field(
        default=(),
        description=(
            "Names of the checks that actually ran "
            "(e.g. 'yaml_syntax', 'pydantic_schema', 'referential_integrity', 'dbt_parse')."
        ),
    )

    @property
    def passed(self) -> bool:
        """True when no ERROR-severity issues were found."""
        return self.summary.errors == 0
