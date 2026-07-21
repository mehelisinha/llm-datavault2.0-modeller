"""Gold-set grading: structural (naming-independent) scoring against a reference.

Conformance (see :mod:`.conformance`) measures whether a plan follows DV2
*conventions*; it cannot tell whether the plan found the *right* entities. For
that the thesis uses a small hand-built gold standard on public, documented
source systems (ServiceNow, CIM/IEC-61968) and grades the modeller's output.

Why structural matching
-----------------------
The raw modeller names hubs after the **source table** (``hub_core_company``)
while the shop convention uses the **concept** (``hub_company``). Matching hubs
by *name* therefore conflates two very different things — did the model find the
right entity, and did it use the right name. So this module matches hubs by
``(source_table, business_key)`` (the entity's identity, naming-independent) and
reports two orthogonal metrics:

* ``entity_f1`` — did the model identify the right entities with the right keys?
  (the correctness signal; should stay high regardless of naming).
* ``naming_adherence`` — over correctly-identified entities, did it use the
  shop's concept name? (the *convention-transfer* signal — the clean place for
  feedback learning to show an effect).

Links and satellites are reported as structural counts (produced vs expected):
their names are naming-confounded the same way, so name-level F1 on them would
be an artifact, not a measurement.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.decisions import ModelingPlan

_GOLD_ROOT = Path(__file__).resolve().parent / "gold_sets"


def _entity_key(source_table: str, business_keys: tuple[str, ...]) -> tuple[str, frozenset[str]]:
    """Naming-independent identity of a hub: its source table + business-key set."""
    return source_table.strip().lower(), frozenset(b.strip().lower() for b in business_keys)


class GoldHub(BaseModel):
    """One expected hub: which source table, which business key, and its concept name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_table: str = Field(min_length=1)
    business_keys: tuple[str, ...] = Field(min_length=1)
    name: str = Field(min_length=1, description="Expected concept name, e.g. hub_company.")


class GoldModel(BaseModel):
    """The expected DV2 structure for one source system (hand-authored)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_id: str = Field(min_length=1)
    hubs: tuple[GoldHub, ...] = ()
    links: tuple[str, ...] = ()  # reference only — count, not name-matched (confounded)
    satellites: tuple[str, ...] = ()  # reference only — count, not name-matched
    # Provenance/wiring only — NOT used by grading. The canonical discovery YAML
    # this gold was authored against, so a reproducible experiment run can resolve
    # system_id -> payload from this single file (no hardcoded paths in runners).
    discovery_payload: str | None = Field(
        default=None, description="Repo-relative path to the discovery YAML for this system."
    )


class PrecisionRecall(BaseModel):
    """Set-comparison metrics for one object kind."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    true_positive: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)

    @property
    def precision(self) -> float:
        denom = self.true_positive + self.false_positive
        return 1.0 if denom == 0 else self.true_positive / denom

    @property
    def recall(self) -> float:
        denom = self.true_positive + self.false_negative
        return 1.0 if denom == 0 else self.true_positive / denom

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 0.0 if (p + r) == 0 else 2 * p * r / (p + r)


class GoldScore(BaseModel):
    """Full grading of a plan against a gold model (structural, naming-independent)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity: PrecisionRecall  # hubs matched by (source_table, business_key)
    naming_matches: int = Field(ge=0)  # of matched entities, how many names match
    matched_entities: int = Field(ge=0)
    expected_links: int = Field(ge=0)
    produced_links: int = Field(ge=0)
    expected_satellites: int = Field(ge=0)
    produced_satellites: int = Field(ge=0)

    @property
    def entity_f1(self) -> float:
        """F1 of entity+key identification — the naming-independent correctness metric."""
        return self.entity.f1

    @property
    def naming_adherence(self) -> float:
        """Fraction of correctly-identified entities that use the shop's concept name.

        1.0 when no entities matched (vacuous). This is the convention-transfer
        signal: it should rise as feedback learning teaches the naming style.
        """
        return 1.0 if self.matched_entities == 0 else self.naming_matches / self.matched_entities

    @property
    def link_ratio(self) -> float:
        """produced / expected links — >1 means over-linking, <1 under-linking."""
        return 0.0 if self.expected_links == 0 else self.produced_links / self.expected_links


def grade_against_gold(plan: ModelingPlan, gold: GoldModel) -> GoldScore:
    """Grade ``plan`` against ``gold``: entity+key F1, naming adherence, structural counts."""
    # First hub wins if two share the same (source_table, business_key) — shouldn't happen.
    model_by_key = {}
    for hub in plan.hubs:
        model_by_key.setdefault(_entity_key(hub.source_table, hub.business_keys), hub)
    gold_by_key = {_entity_key(gh.source_table, gh.business_keys): gh for gh in gold.hubs}

    matched = set(model_by_key) & set(gold_by_key)
    entity = PrecisionRecall(
        true_positive=len(matched),
        false_positive=len(set(model_by_key) - matched),
        false_negative=len(set(gold_by_key) - matched),
    )
    naming_matches = sum(
        1
        for k in matched
        if model_by_key[k].name.strip().lower() == gold_by_key[k].name.strip().lower()
    )
    return GoldScore(
        entity=entity,
        naming_matches=naming_matches,
        matched_entities=len(matched),
        expected_links=len(gold.links),
        produced_links=len(plan.links),
        expected_satellites=len(gold.satellites),
        produced_satellites=len(plan.satellites),
    )


class CorrectionReport(BaseModel):
    """Structural edits needed to turn a produced plan into the gold reference.

    An objective, ground-truth-based proxy for **human correction effort** (H3b):
    how many manual actions a reviewer would take to bring a machine-produced plan
    up to the approvable (gold) model. Deliberately conservative and simple so it
    is defensible without a timed human study.

    Counting model (documented so the number is reproducible, not a black box):

    * ``hub_add`` — gold hubs with no matching produced hub (by source_table +
      business_key): the entity must be created.
    * ``hub_delete`` — produced hubs matching no gold hub: a spurious entity to
      remove. A **mis-keyed** hub (right table, wrong key) therefore costs 2 — one
      delete + one add — rather than an in-place re-key. This is the conservative
      choice and is stated as such.
    * ``hub_rename`` — matched hubs whose name differs from the gold concept name.
    * ``link_delta`` / ``sat_delta`` — the **count** difference vs gold (links and
      satellites are naming-confounded, so a net-count floor is used rather than
      name matching). This under-counts a "wrong one present + right one missing"
      pair as a single edit — hence a floor, not an exact figure.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    hub_add: int = Field(ge=0)
    hub_delete: int = Field(ge=0)
    hub_rename: int = Field(ge=0)
    link_delta: int = Field(ge=0)
    sat_delta: int = Field(ge=0)

    @property
    def total(self) -> int:
        """Total structural edits — the correction-step count."""
        return self.hub_add + self.hub_delete + self.hub_rename + self.link_delta + self.sat_delta


def correction_steps(plan: ModelingPlan, gold: GoldModel) -> CorrectionReport:
    """Count the structural edits to turn ``plan`` into ``gold`` (see CorrectionReport)."""
    model_by_key: dict[tuple[str, frozenset[str]], object] = {}
    for hub in plan.hubs:
        model_by_key.setdefault(_entity_key(hub.source_table, hub.business_keys), hub)
    gold_by_key = {_entity_key(gh.source_table, gh.business_keys): gh for gh in gold.hubs}

    matched = set(model_by_key) & set(gold_by_key)
    hub_rename = sum(
        1
        for k in matched
        if model_by_key[k].name.strip().lower() != gold_by_key[k].name.strip().lower()
    )
    return CorrectionReport(
        hub_add=len(set(gold_by_key) - matched),
        hub_delete=len(set(model_by_key) - matched),
        hub_rename=hub_rename,
        link_delta=abs(len(plan.links) - len(gold.links)),
        sat_delta=abs(len(plan.satellites) - len(gold.satellites)),
    )


def build_from_scratch_steps(gold: GoldModel) -> int:
    """Manual-arm effort: every gold object is created from scratch (one action each)."""
    return len(gold.hubs) + len(gold.links) + len(gold.satellites)


def load_gold_models(root: Path | str | None = None) -> dict[str, GoldModel]:
    """Load every ``*.yml`` gold model under ``root`` (defaults to gold_sets/).

    Returns a mapping ``system_id -> GoldModel``. Files that do not parse into a
    valid :class:`GoldModel` are skipped so a half-authored gold set never breaks
    the whole experiment run.
    """
    base = Path(root) if root is not None else _GOLD_ROOT
    out: dict[str, GoldModel] = {}
    if not base.is_dir():
        return out
    for path in sorted(base.glob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            model = GoldModel.model_validate(data)
        except Exception:
            continue
        out[model.system_id] = model
    return out


__all__ = [
    "CorrectionReport",
    "GoldHub",
    "GoldModel",
    "GoldScore",
    "PrecisionRecall",
    "build_from_scratch_steps",
    "correction_steps",
    "grade_against_gold",
    "load_gold_models",
]
