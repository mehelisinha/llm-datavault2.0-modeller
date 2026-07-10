"""Gold-set grading: precision / recall / F1 against a hand-modelled reference.

Conformance (see :mod:`.conformance`) measures whether a plan follows DV2
*conventions*; it cannot tell whether the plan found the *right* entities. For
that the thesis uses a small hand-built gold standard on public, documented
source systems (ServiceNow, CIM/IEC-61968) and grades the modeller's output
against it: did it produce the expected hubs / links / satellites, and did it
pick the expected business keys?

Gold models are deliberately light — expected object names plus, for hubs, the
expected business-key set. They are authored as YAML under ``gold_sets/`` and
loaded with :func:`load_gold_models`. Matching is by normalised name so a plan
that renames ``hub_user`` -> ``hub_users`` is scored as a miss, which is the
honest, reproducible behaviour for a benchmark.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.decisions import ModelingPlan

_GOLD_ROOT = Path(__file__).resolve().parent / "gold_sets"


def _norm(name: str) -> str:
    return name.strip().lower()


class GoldModel(BaseModel):
    """The expected DV2 structure for one source system (hand-authored)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_id: str = Field(min_length=1)
    # hub name -> expected business-key set (order-insensitive, case-insensitive).
    hubs: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    links: tuple[str, ...] = ()
    satellites: tuple[str, ...] = ()


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
    """Full grading of a plan against a gold model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hubs: PrecisionRecall
    links: PrecisionRecall
    satellites: PrecisionRecall
    business_key_matches: int = Field(ge=0)
    business_key_total: int = Field(ge=0)

    @property
    def business_key_accuracy(self) -> float:
        """Fraction of correctly-identified hubs whose business key set is exact."""
        return (
            1.0
            if self.business_key_total == 0
            else self.business_key_matches / self.business_key_total
        )

    @property
    def macro_f1(self) -> float:
        """Unweighted mean F1 across the three object kinds."""
        return (self.hubs.f1 + self.links.f1 + self.satellites.f1) / 3


def _pr(produced: set[str], gold: set[str]) -> PrecisionRecall:
    return PrecisionRecall(
        true_positive=len(produced & gold),
        false_positive=len(produced - gold),
        false_negative=len(gold - produced),
    )


def grade_against_gold(plan: ModelingPlan, gold: GoldModel) -> GoldScore:
    """Grade ``plan`` against ``gold``: per-kind P/R/F1 + business-key accuracy."""
    p_hubs = {_norm(h.name) for h in plan.hubs}
    g_hubs = {_norm(n) for n in gold.hubs}
    p_links = {_norm(link.name) for link in plan.links}
    g_links = {_norm(n) for n in gold.links}
    p_sats = {_norm(s.name) for s in plan.satellites}
    g_sats = {_norm(n) for n in gold.satellites}

    # Business-key accuracy over hubs the plan correctly identified.
    gold_bk = {_norm(name): {k.lower() for k in keys} for name, keys in gold.hubs.items()}
    matched = p_hubs & g_hubs
    correct = 0
    for hub in plan.hubs:
        key = _norm(hub.name)
        if key in matched and {b.lower() for b in hub.business_keys} == gold_bk.get(key, set()):
            correct += 1

    return GoldScore(
        hubs=_pr(p_hubs, g_hubs),
        links=_pr(p_links, g_links),
        satellites=_pr(p_sats, g_sats),
        business_key_matches=correct,
        business_key_total=len(matched),
    )


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
    "GoldModel",
    "GoldScore",
    "PrecisionRecall",
    "grade_against_gold",
    "load_gold_models",
]
