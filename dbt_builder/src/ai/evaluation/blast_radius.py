"""Blast-radius analysis: how far a wrong object propagates through the plan.

Not every modelling error costs the same. A wrong *hub* business key breaks
every satellite hanging off it and every link that references its hash key; a
wrong *satellite* payload breaks only itself. The blast radius of an object is
the number of downstream objects that depend on it, so an error's severity can
be weighted by the radius of the object it lands on — the "blast radius study".

Dependency edges in a raw vault (this contract):
* satellite  -> its parent hub          (sat depends on hub)
* link       -> each hub it references   (link depends on hubs via fk hash keys)

So a hub's blast radius = (#satellites on it) + (#links referencing it). Links
and satellites are leaves here (nothing in the raw vault depends on them), so
their radius is 0.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.evaluation.conformance import ConformanceReport


class BlastRadiusReport(BaseModel):
    """Per-object downstream-dependency counts plus summary statistics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    per_object: dict[str, int] = Field(
        default_factory=dict, description="object name -> number of downstream dependents"
    )

    @property
    def max_radius(self) -> int:
        return max(self.per_object.values(), default=0)

    @property
    def total_dependents(self) -> int:
        return sum(self.per_object.values())

    def hotspots(self, limit: int = 5) -> tuple[tuple[str, int], ...]:
        """Top objects by blast radius (desc radius, then name) — the fragile ones."""
        ranked = sorted(self.per_object.items(), key=lambda kv: (-kv[1], kv[0]))
        return tuple(ranked[:limit])


def plan_blast_radius(plan: ModelingPlan) -> BlastRadiusReport:
    """Compute the downstream-dependent count for every object in ``plan``."""
    per_object: dict[str, int] = {}
    for hub in plan.hubs:
        sats = sum(1 for s in plan.satellites if s.parent_hub == hub.name)
        links = sum(1 for ln in plan.links if hub.hash_key in ln.fk_columns)
        per_object[hub.name] = sats + links
    for link in plan.links:
        per_object[link.name] = 0
    for sat in plan.satellites:
        per_object[sat.name] = 0
    return BlastRadiusReport(per_object=per_object)


def weighted_error_impact(plan: ModelingPlan, report: ConformanceReport) -> int:
    """Sum of ``1 + blast_radius`` over every conformance issue's object.

    Weights each error by how many downstream objects the offending object
    carries, so an error on a high-fan-out hub counts more than one on a leaf
    satellite. Plan-level issues (object_name == '') contribute 1 each. Higher =
    worse; the study reports how retrieval lowers this vs the raw issue count.
    """
    radius = plan_blast_radius(plan).per_object
    return sum(1 + radius.get(issue.object_name, 0) for issue in report.issues)


__all__ = ["BlastRadiusReport", "plan_blast_radius", "weighted_error_impact"]
