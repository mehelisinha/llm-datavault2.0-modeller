"""Grounding check — the hallucination metric.

Every Data Vault plan names things that must **exist in the source**: each object's
source table, each hub's business-key column(s), and each satellite's payload
columns. A *fabricated* reference — a table or column the discovery payload does
not contain — is a hallucination: the model invented source structure.

This is distinct from the conformance checks ``link_fk_unresolved`` and
``satellite_orphan``, which detect **internal** dangling references (plan-vs-plan
consistency). Grounding is **plan-vs-source**: it is the only metric here that can
catch the canonical LLM failure mode of inventing data that isn't there.

Requires no gold set — only the plan and the discovery payload it was generated
from — so it can be computed on every run of any system, including ones with no
hand-authored reference model. Pure and deterministic.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.contracts.payloads import DiscoveryPayload


class GroundingReport(BaseModel):
    """Result of checking every source reference in a plan against the payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_references: int = Field(ge=0)
    fabricated_references: int = Field(ge=0)
    fabricated_tables: tuple[str, ...] = ()
    fabricated_columns: tuple[str, ...] = ()

    @property
    def hallucination_rate(self) -> float:
        """Fabricated ÷ total references. 0.0 = fully grounded (no invention)."""
        return 0.0 if self.total_references == 0 else (
            self.fabricated_references / self.total_references
        )

    @property
    def grounding_rate(self) -> float:
        """Fraction of references that genuinely exist in the source (1 - hallucination)."""
        return 1.0 - self.hallucination_rate


def check_grounding(plan: ModelingPlan, payload: DiscoveryPayload) -> GroundingReport:
    """Verify every source reference in ``plan`` against the discovery ``payload``."""
    columns_by_table = {
        t.name.strip().lower(): {c.name.strip().lower() for c in t.columns}
        for t in payload.tables
    }
    return check_grounding_from_columns(plan, columns_by_table)


def check_grounding_from_columns(
    plan: ModelingPlan, columns_by_table: Mapping[str, set[str]]
) -> GroundingReport:
    """Verify every source table / business key / payload column the plan names.

    ``columns_by_table`` maps lower-cased source-table name → set of lower-cased
    column names. Accepting the plain mapping (rather than a full payload) lets the
    pipeline compute grounding from its bronze snapshot, and keeps this the single
    implementation both callers share.

    Counts one *reference* per (object → source table) and one per named column
    (hub business keys, satellite payload columns). Link ``fk_columns`` are hub
    hash keys, not source columns, so they are excluded here — their integrity is
    already covered by the ``link_fk_unresolved`` conformance check.
    """
    total = 0
    fabricated_tables: list[str] = []
    fabricated_columns: list[str] = []

    def _check_table(source_table: str, obj_name: str) -> str | None:
        """Count the table reference; return its key when it exists, else None."""
        nonlocal total
        total += 1
        key = source_table.strip().lower()
        if key not in columns_by_table:
            fabricated_tables.append(f"{obj_name} -> table '{source_table}'")
            return None
        return key

    def _check_columns(key: str | None, columns, obj_name: str, kind: str) -> None:
        nonlocal total
        for col in columns:
            total += 1
            if key is None:
                # Table itself is fabricated — its columns cannot be verified, and
                # counting them as fabricated too reflects the real damage.
                fabricated_columns.append(f"{obj_name} -> {kind} '{col}' (on unknown table)")
                continue
            if col.strip().lower() not in columns_by_table[key]:
                fabricated_columns.append(f"{obj_name} -> {kind} '{col}'")

    for hub in plan.hubs:
        key = _check_table(hub.source_table, hub.name)
        _check_columns(key, hub.business_keys, hub.name, "business key")
    for sat in plan.satellites:
        key = _check_table(sat.source_table, sat.name)
        _check_columns(key, sat.payload, sat.name, "payload column")
    for link in plan.links:
        _check_table(link.source_table, link.name)

    return GroundingReport(
        total_references=total,
        fabricated_references=len(fabricated_tables) + len(fabricated_columns),
        fabricated_tables=tuple(fabricated_tables),
        fabricated_columns=tuple(fabricated_columns),
    )


__all__ = ["GroundingReport", "check_grounding", "check_grounding_from_columns"]
