"""Input -> output coverage: did every source table become at least one object?

A DV2 model should account for every actionable source table. A table that
produces no hub / link / satellite is a silent drop — usually a modelling miss.
This measures the mapping from the *input* (source tables) to the *output*
(plan objects), the "input to output" dimension of the study.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.decisions import ModelingPlan


class CoverageReport(BaseModel):
    """How completely a plan covers its source tables."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_tables: int = Field(ge=0)
    covered_tables: int = Field(ge=0)
    hubs: int = Field(ge=0)
    links: int = Field(ge=0)
    satellites: int = Field(ge=0)
    uncovered: tuple[str, ...] = Field(
        default=(), description="Source tables that produced no plan object."
    )

    @property
    def coverage_ratio(self) -> float:
        """Fraction of source tables represented by >= 1 object (1.0 if none)."""
        return 1.0 if self.source_tables == 0 else self.covered_tables / self.source_tables


def coverage(plan: ModelingPlan, source_tables: Iterable[str]) -> CoverageReport:
    """Return input->output :class:`CoverageReport` for ``plan`` over ``source_tables``.

    Matching is case-insensitive on the bare source-table name (the same field
    every decision carries). Source-table names are de-duplicated first.
    """
    tables = {t.lower() for t in source_tables}
    produced = {d.source_table.lower() for d in (*plan.hubs, *plan.links, *plan.satellites)}
    covered = tables & produced
    return CoverageReport(
        source_tables=len(tables),
        covered_tables=len(covered),
        hubs=len(plan.hubs),
        links=len(plan.links),
        satellites=len(plan.satellites),
        uncovered=tuple(sorted(tables - produced)),
    )


__all__ = ["CoverageReport", "coverage"]
