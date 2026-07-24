"""Risk-assessment contracts produced by the pipeline supervisor.

Design notes
------------
* All models are frozen so they can be safely embedded in the immutable
  :class:`~dbt_builder.src.ai.contracts.pipeline_run.PipelineRun` without
  defensive copying.
* :class:`RiskAssessment` is always deterministic (no LLM calls) so it is
  cheap to recompute and safe to serialise as JSON in the run store.
* :class:`RiskKind` is a closed enum — every new signal kind must be added
  here so the UI can display a stable label and help text.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class RiskSeverity(str, Enum):
    """Severity tier for a single risk signal."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskKind(str, Enum):
    """Enumeration of all risk signals the supervisor can detect.

    Names are stable machine-readable identifiers; the UI maps them to
    human-readable labels.
    """

    HIGH_NEW_TABLE_VOLUME = "high_new_table_volume"
    HIGH_DRIFT_FRACTION = "high_drift_fraction"
    BREAKING_SCHEMA_CHANGE = "breaking_schema_change"
    ORPHANED_ENTITIES_PRESENT = "orphaned_entities_present"
    LOW_CONFIDENCE_DECISIONS = "low_confidence_decisions"
    EMPTY_PLAN = "empty_plan"
    VALIDATION_ERRORS = "validation_errors"
    VALIDATION_WARNINGS = "validation_warnings"


class SupervisionRecommendation(str, Enum):
    """Top-level action recommended after risk assessment."""

    PASS = "pass"  # proceed automatically
    PAUSE = "pause"  # surface to human before next step


class RiskSignal(BaseModel):
    """A single detected risk condition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: RiskKind
    severity: RiskSeverity
    detail: str  # human-readable explanation


class RiskAssessment(BaseModel):
    """Aggregated risk assessment produced after one pipeline step.

    The :attr:`recommendation` is derived from :attr:`signals`:

    * Any HIGH-severity signal → PAUSE.
    * Two or more MEDIUM-severity signals → PAUSE.
    * LOW-only (or no signals) → PASS.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    assessed_after_step: str  # PipelineStepName.value
    signals: tuple[RiskSignal, ...] = ()
    max_severity: RiskSeverity
    recommendation: SupervisionRecommendation
