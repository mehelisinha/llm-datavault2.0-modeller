"""Reproducible experiment harness — one declarative runner for every study.

Experiments 1–4 (ablation, learning curve, cross-domain control, end-to-end
reviewer + error-taxonomy shift) are all the *same* operation with different
knobs: build a modeller under some learning condition, optionally run the plan
reviewer, and grade the raw (and reviewed) plan. This module captures that once,
declaratively, so a study is specified by data — a list of :class:`Condition`s,
a list of system ids, and seeds — not by a bespoke script with hardcoded paths.

Design
------
* **No hardcoding.** A system is named by ``system_id``; its gold set *and* its
  discovery-payload path both come from the one ``gold_sets/<x>.yml`` file
  (:attr:`GoldModel.discovery_payload`). Seeds, k, leave-one-out catalogs, and
  whether to review are all parameters.
* **DRY.** The modeller/reviewer wiring lives in :func:`build_modeller` /
  :func:`run_condition` — the same wiring the four experiments used, in one place.
* **Testable.** Every LLM-touching dependency (agent factory, corpus loader,
  reviewer factory, discovery) is injected with a production default, so the
  control flow is unit-tested with fakes and no network. The pure helpers
  (:func:`parse_condition`, :func:`taxonomy_shift`) have no dependencies at all.
* **Integrity.** Metrics come straight from :func:`evaluate_plan`; nothing here
  transforms a score. Raw and reviewed plans are graded identically.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.evaluation.experiment import PlanMetrics, evaluate_plan
from dbt_builder.src.ai.evaluation.gold import GoldModel, load_gold_models

# ── Declarative condition ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class Condition:
    """One experimental condition (an *arm*).

    Parameters
    ----------
    label
        Human-readable arm name used in results (e.g. ``"off"``, ``"loo_k10"``).
    k
        Approved examples retrieved into the modeller prompt. ``0`` disables
        feedback learning entirely (the OFF baseline).
    exclude_catalogs
        Corpus catalogs to hold out — the leave-one-out guard against train/test
        leakage. Empty means "use the whole corpus".
    review
        When true, the gpt-5.2 plan reviewer runs on the modeller's draft and the
        reviewed plan is graded too (the end-to-end/product condition).
    producer
        Which arm generates the plan: ``"modeller"`` (the LLM, default) or
        ``"heuristic"`` (the deterministic rule-based baseline). The heuristic
        ignores ``k`` and ``exclude_catalogs`` (it has no corpus).
    """

    label: str
    k: int = 0
    exclude_catalogs: tuple[str, ...] = ()
    review: bool = False
    producer: str = "modeller"


def parse_condition(spec: str) -> Condition:
    """Parse a ``label[:key=val,...]`` condition spec into a :class:`Condition`.

    Keys (all optional): ``k`` (int), ``exclude`` (``+``-separated catalog names),
    ``review`` (``1``/``true``/``yes`` = on). Examples::

        "off"                                    -> k=0
        "on:k=10"                                -> k=10, full corpus
        "loo:k=10,exclude=iec_cim+edh_silver"    -> leave-one-out at k=10
        "e2e:k=10,review=1"                      -> end-to-end with reviewer
        "det:producer=heuristic"                 -> deterministic rule-based arm

    Pure — no I/O. Raises ``ValueError`` on a malformed spec so a typo in a study
    definition fails loudly rather than silently running the wrong arm.
    """
    label, _, rest = spec.partition(":")
    label = label.strip()
    if not label:
        raise ValueError(f"condition spec {spec!r} has an empty label")
    k = 0
    exclude: tuple[str, ...] = ()
    review = False
    producer = "modeller"
    for part in (p for p in rest.split(",") if p.strip()):
        key, sep, val = part.partition("=")
        key, val = key.strip(), val.strip()
        if not sep:
            raise ValueError(f"condition spec {spec!r}: '{part}' is not key=value")
        if key == "k":
            k = int(val)
        elif key == "exclude":
            exclude = tuple(c for c in val.split("+") if c)
        elif key == "review":
            review = val.lower() in {"1", "true", "yes", "on"}
        elif key == "producer":
            if val not in {"modeller", "heuristic"}:
                raise ValueError(
                    f"condition spec {spec!r}: producer must be 'modeller' or 'heuristic'"
                )
            producer = val
        else:
            raise ValueError(f"condition spec {spec!r}: unknown key {key!r}")
    return Condition(
        label=label, k=k, exclude_catalogs=exclude, review=review, producer=producer
    )


# ── Error-taxonomy shift (pure) ───────────────────────────────────────────────


class TaxonomyShift(BaseModel):
    """Per-``IssueType`` change between a raw and a reviewed plan.

    ``resolved`` = fixed by the reviewer (raw had more), ``introduced`` = newly
    caused by the reviewer (reviewed has more), ``persisted`` = present in both
    (min of the two counts). Reported per category — the resolution analysis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    resolved: dict[str, int] = Field(default_factory=dict)
    introduced: dict[str, int] = Field(default_factory=dict)
    persisted: dict[str, int] = Field(default_factory=dict)

    @property
    def net_resolved(self) -> int:
        """Total issues removed minus issues introduced (>0 = net improvement)."""
        return sum(self.resolved.values()) - sum(self.introduced.values())


def taxonomy_shift(raw: Mapping[str, int], reviewed: Mapping[str, int]) -> TaxonomyShift:
    """Diff two ``issues_by_type`` histograms into resolved/introduced/persisted.

    Pure: works on plain count maps, so it composes over any aggregation (one
    plan, or summed over seeds/systems). Zero-count categories are omitted.
    """
    keys = set(raw) | set(reviewed)
    resolved, introduced, persisted = {}, {}, {}
    for key in keys:
        r, v = int(raw.get(key, 0)), int(reviewed.get(key, 0))
        if r > v:
            resolved[key] = r - v
        elif v > r:
            introduced[key] = v - r
        if min(r, v) > 0:
            persisted[key] = min(r, v)
    return TaxonomyShift(resolved=resolved, introduced=introduced, persisted=persisted)


# ── Result record ─────────────────────────────────────────────────────────────


class StageRecord(BaseModel):
    """One (system, condition, seed) trial: raw metrics + optional reviewed metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_id: str
    condition: str
    seed: int
    reviewer_deployment: str | None = None
    t_model_s: float = Field(ge=0.0)
    t_review_s: float = Field(ge=0.0, default=0.0)
    raw: PlanMetrics
    reviewed: PlanMetrics | None = None

    @property
    def shift(self) -> TaxonomyShift | None:
        """Error-taxonomy shift from raw to reviewed (None when not reviewed)."""
        if self.reviewed is None:
            return None
        return taxonomy_shift(self.raw.issues_by_type, self.reviewed.issues_by_type)


# ── System resolution (single source of truth) ────────────────────────────────


def resolve_payload_path(gold: GoldModel) -> str:
    """Return the discovery-payload path declared on ``gold`` or raise.

    The gold file is the one place a system's payload location is recorded, so a
    missing ``discovery_payload`` is a setup error worth failing on explicitly.
    """
    if not gold.discovery_payload:
        raise ValueError(
            f"gold set for {gold.system_id!r} has no 'discovery_payload' — add it so "
            "the runner can resolve the system without a hardcoded path."
        )
    return gold.discovery_payload


# ── Wiring (injectable; production defaults) ──────────────────────────────────


def _default_agent_factory(**kwargs):
    from dbt_builder.src.ai.agents.modeller import get_modelling_agent

    return get_modelling_agent(**kwargs)


def _default_corpus_loader(settings, *, exclude_catalogs=()):
    from dbt_builder.src.ai.agents.modeller import _load_reference_corpus

    return _load_reference_corpus(settings, exclude_catalogs=exclude_catalogs)


def _default_reviewer_factory(*, settings):
    from dbt_builder.src.ai.agents.plan_reviewer import get_plan_reviewer

    return get_plan_reviewer(settings=settings)


def _default_discover(path: str):
    from dbt_builder.src.ai.discovery.schema_discovery import discover_from_yaml

    return discover_from_yaml(path)


def _default_heuristic_factory():
    from dbt_builder.src.ai.evaluation.baselines import HeuristicClassifier

    return HeuristicClassifier()


@dataclass(frozen=True)
class Wiring:
    """Injectable dependencies for :func:`run_condition` / :func:`run_study`.

    Defaults call the real modeller, corpus loader, reviewer, discovery, and the
    deterministic heuristic baseline. Tests pass fakes so the control flow runs
    with no LLM and no network.
    """

    agent_factory: Callable = _default_agent_factory
    corpus_loader: Callable = _default_corpus_loader
    reviewer_factory: Callable = _default_reviewer_factory
    discover: Callable = _default_discover
    heuristic_factory: Callable = _default_heuristic_factory


# Immutable default set of production dependencies (shared; frozen dataclass).
_DEFAULT_WIRING = Wiring()


def build_modeller(
    condition: Condition, *, settings, samples: int = 1, wiring: Wiring | None = None
):
    """Construct the plan producer for ``condition`` (the one wiring point).

    ``producer="heuristic"`` returns the deterministic rule-based baseline
    (ignores ``k``/corpus). Otherwise the LLM modeller: ``k <= 0`` → learning OFF
    (retrieval limit 0); else load the corpus with the condition's leave-one-out
    exclusions and cap retrieval at ``k``. Centralised so every study shares it.
    """
    wiring = wiring or _DEFAULT_WIRING
    if condition.producer == "heuristic":
        return wiring.heuristic_factory()
    if condition.k <= 0:
        return wiring.agent_factory(settings=settings, samples=samples, reference_limit_override=0)
    loader = wiring.corpus_loader(settings, exclude_catalogs=condition.exclude_catalogs)
    return wiring.agent_factory(
        settings=settings,
        samples=samples,
        reference_loader_override=loader,
        reference_limit_override=condition.k,
    )


def run_condition(
    *,
    gold: GoldModel,
    payload,
    condition: Condition,
    seed: int,
    settings,
    samples: int = 1,
    wiring: Wiring | None = None,
) -> StageRecord:
    """Run one (system, condition, seed) trial and grade raw (+ reviewed) plans."""
    wiring = wiring or _DEFAULT_WIRING
    cfg = settings.model_copy(update={"llm_seed": seed})
    agent = build_modeller(condition, settings=cfg, samples=samples, wiring=wiring)
    src = tuple(t.name for t in payload.tables)
    tech = cfg.technical_payload_column_set()

    t0 = time.perf_counter()
    raw_plan: ModelingPlan = agent.propose(payload)
    t_model = time.perf_counter() - t0
    m_raw = evaluate_plan(raw_plan, source_tables=src, gold=gold, technical_columns=tech)

    reviewer = wiring.reviewer_factory(settings=cfg) if condition.review else None
    m_rev = None
    t_review = 0.0
    reviewer_dep = None
    if reviewer is not None:
        reviewer_dep = getattr(reviewer, "deployment", None)
        t1 = time.perf_counter()
        reviewed_plan = reviewer.review(raw_plan, payload)
        t_review = time.perf_counter() - t1
        m_rev = evaluate_plan(reviewed_plan, source_tables=src, gold=gold, technical_columns=tech)

    return StageRecord(
        system_id=gold.system_id,
        condition=condition.label,
        seed=seed,
        reviewer_deployment=reviewer_dep,
        t_model_s=round(t_model, 2),
        t_review_s=round(t_review, 2),
        raw=m_raw,
        reviewed=m_rev,
    )


def run_study(
    *,
    systems: Sequence[str],
    conditions: Sequence[Condition],
    seeds: Sequence[int],
    settings,
    samples: int = 1,
    golds: Mapping[str, GoldModel] | None = None,
    wiring: Wiring | None = None,
    on_record: Callable[[StageRecord], None] | None = None,
) -> list[StageRecord]:
    """Run every (system × condition × seed) trial; return the flat record list.

    ``systems`` are gold ``system_id``s; each is resolved to its gold + discovery
    payload from the one gold file. ``on_record`` (optional) is called after each
    trial for live progress logging. Discovery payloads are loaded once per system.
    """
    wiring = wiring or _DEFAULT_WIRING
    labels = [c.label for c in conditions]
    dupes = sorted({lbl for lbl in labels if labels.count(lbl) > 1})
    if dupes:
        # summarise() groups by (system, condition.label); duplicate labels would
        # silently merge distinct arms (e.g. two 'on' arms at different k) into one
        # average. Fail loud so a study definition can't corrupt its own table.
        raise ValueError(
            f"duplicate condition labels {dupes} — give each arm a unique label "
            "(e.g. k1:k=1, k10:k=10), since results are grouped by label."
        )
    golds = golds if golds is not None else load_gold_models()
    records: list[StageRecord] = []
    for system_id in systems:
        gold = golds.get(system_id)
        if gold is None:
            raise ValueError(
                f"no gold set for system_id {system_id!r} (have: {sorted(golds)})"
            )
        payload = wiring.discover(resolve_payload_path(gold))
        for condition in conditions:
            for seed in seeds:
                rec = run_condition(
                    gold=gold,
                    payload=payload,
                    condition=condition,
                    seed=seed,
                    settings=settings,
                    samples=samples,
                    wiring=wiring,
                )
                records.append(rec)
                if on_record is not None:
                    on_record(rec)
    return records


# ── Aggregation ───────────────────────────────────────────────────────────────

_MEAN_FIELDS = (
    "gold_entity_f1",
    "gold_naming_adherence",
    "gold_link_ratio",
    "correction_steps",
    "conformance_score",
    "issue_count",
    "weighted_error_impact",
    "max_blast_radius",
    "n_hubs",
    "n_links",
    "n_satellites",
)


def _mean(values: Sequence[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def _sum_histograms(hists: Sequence[Mapping[str, int]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for hist in hists:
        for key, val in hist.items():
            if val:
                out[key] = out.get(key, 0) + val
    return out


@dataclass(frozen=True)
class StageSummary:
    """Mean metrics + summed taxonomy for one stage (raw or reviewed) of a cell."""

    means: dict[str, float | None] = field(default_factory=dict)
    issues_by_type: dict[str, int] = field(default_factory=dict)
    naming_per_seed: tuple[float | None, ...] = ()


def summarise(records: Sequence[StageRecord]) -> dict[str, dict[str, StageSummary | TaxonomyShift]]:
    """Aggregate records into per-(system/condition) raw & reviewed summaries.

    Returns ``{"system/condition": {"raw": StageSummary, "reviewed": StageSummary
    | None, "shift": TaxonomyShift | None}}``. Means are over seeds; the taxonomy
    shift is computed on the summed raw vs summed reviewed histograms.
    """
    keys: list[str] = []
    grouped: dict[str, list[StageRecord]] = {}
    for rec in records:
        key = f"{rec.system_id}/{rec.condition}"
        if key not in grouped:
            grouped[key] = []
            keys.append(key)
        grouped[key].append(rec)

    out: dict[str, dict[str, StageSummary | TaxonomyShift]] = {}
    for key in keys:
        grp = grouped[key]
        raw = StageSummary(
            means={f: _mean([getattr(r.raw, f) for r in grp]) for f in _MEAN_FIELDS},
            issues_by_type=_sum_histograms([r.raw.issues_by_type for r in grp]),
            naming_per_seed=tuple(r.raw.gold_naming_adherence for r in grp),
        )
        cell: dict[str, StageSummary | TaxonomyShift] = {"raw": raw, "reviewed": None, "shift": None}
        reviewed = [r for r in grp if r.reviewed is not None]
        if reviewed:
            rev = StageSummary(
                means={f: _mean([getattr(r.reviewed, f) for r in reviewed]) for f in _MEAN_FIELDS},
                issues_by_type=_sum_histograms([r.reviewed.issues_by_type for r in reviewed]),
                naming_per_seed=tuple(r.reviewed.gold_naming_adherence for r in reviewed),
            )
            cell["reviewed"] = rev
            cell["shift"] = taxonomy_shift(raw.issues_by_type, rev.issues_by_type)
        out[key] = cell
    return out


__all__ = [
    "Condition",
    "StageRecord",
    "StageSummary",
    "TaxonomyShift",
    "Wiring",
    "build_modeller",
    "parse_condition",
    "resolve_payload_path",
    "run_condition",
    "run_study",
    "summarise",
    "taxonomy_shift",
]
