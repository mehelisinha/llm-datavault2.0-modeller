"""Reproducible study harness: condition parsing, wiring, taxonomy shift, runner.

All LLM-touching dependencies are injected as fakes, so these tests exercise the
control flow with no network and no Azure creds. Metrics come from the real
``evaluate_plan`` over small real plans, so the taxonomy-shift assertions are
genuine, not mocked.
"""

from __future__ import annotations

import pytest

from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.evaluation.gold import GoldHub, GoldModel
from dbt_builder.src.ai.evaluation.study import (
    Condition,
    Wiring,
    build_modeller,
    parse_condition,
    resolve_payload_path,
    run_condition,
    run_study,
    summarise,
    taxonomy_shift,
)

# ── fakes ─────────────────────────────────────────────────────────────────────


class _Col:
    def __init__(self, name: str) -> None:
        self.name = name


class _Payload:
    def __init__(self, *tables: str) -> None:
        self.tables = tuple(_Col(t) for t in tables)


class _Settings:
    """Minimal stand-in for AISettings used by the harness."""

    def __init__(self, llm_seed: int = -1) -> None:
        self.llm_seed = llm_seed

    def model_copy(self, *, update: dict) -> "_Settings":
        s = _Settings(self.llm_seed)
        for k, v in update.items():
            setattr(s, k, v)
        return s

    def technical_payload_column_set(self) -> frozenset[str]:
        return frozenset()


class _Agent:
    def __init__(self, plan: ModelingPlan) -> None:
        self._plan = plan

    def propose(self, payload) -> ModelingPlan:
        return self._plan


class _Reviewer:
    deployment = "gpt-5.2-fake"

    def __init__(self, plan: ModelingPlan) -> None:
        self._plan = plan

    def review(self, plan, payload) -> ModelingPlan:
        return self._plan


def _hub(name: str) -> HubDecision:
    return HubDecision(name=name, source_table="cust", business_keys=("email",), hash_key="HK_CUST")


def _sat(parent: str) -> SatelliteDecision:
    return SatelliteDecision(
        name="sat_cust_details", source_table="cust", parent_hub=parent,
        hash_key="HK_CUST", hashdiff="HD_CUST", payload=("name",),
    )


def _raw_plan() -> ModelingPlan:
    # 'customer' lacks the hub_ prefix -> one NAMING issue; sat keeps it otherwise clean.
    return ModelingPlan(system_id="X", hubs=(_hub("customer"),), satellites=(_sat("customer"),))


def _reviewed_plan() -> ModelingPlan:
    # reviewer fixes the name -> NAMING issue resolved.
    return ModelingPlan(system_id="X", hubs=(_hub("hub_customer"),), satellites=(_sat("hub_customer"),))


def _gold() -> GoldModel:
    return GoldModel(
        system_id="X",
        hubs=(GoldHub(source_table="cust", business_keys=("email",), name="hub_customer"),),
        discovery_payload="poc/metadata/x_discovery.yaml",
    )


# ── parse_condition ───────────────────────────────────────────────────────────


def test_parse_condition_bare_label():
    assert parse_condition("off") == Condition(label="off", k=0)


def test_parse_condition_full():
    c = parse_condition("loo:k=10,exclude=iec_cim+edh_silver,review=1")
    assert c == Condition(label="loo", k=10, exclude_catalogs=("iec_cim", "edh_silver"), review=True)


@pytest.mark.parametrize("val,expected", [("1", True), ("true", True), ("yes", True), ("0", False)])
def test_parse_condition_review_flag(val, expected):
    assert parse_condition(f"e2e:review={val}").review is expected


def test_parse_condition_producer_heuristic():
    assert parse_condition("det:producer=heuristic").producer == "heuristic"


def test_parse_condition_producer_defaults_modeller():
    assert parse_condition("off").producer == "modeller"


def test_parse_condition_rejects_bad_producer():
    with pytest.raises(ValueError, match="producer must be"):
        parse_condition("x:producer=magic")


def test_parse_condition_rejects_empty_label():
    with pytest.raises(ValueError):
        parse_condition(":k=3")


def test_parse_condition_rejects_unknown_key():
    with pytest.raises(ValueError):
        parse_condition("x:bogus=1")


def test_parse_condition_rejects_non_kv():
    with pytest.raises(ValueError):
        parse_condition("x:k")


# ── taxonomy_shift ────────────────────────────────────────────────────────────


def test_taxonomy_shift_resolved_introduced_persisted():
    shift = taxonomy_shift({"naming": 3, "orphan": 1}, {"naming": 1, "link_fk": 2})
    assert shift.resolved == {"naming": 2, "orphan": 1}  # orphan only in raw -> resolved
    assert shift.introduced == {"link_fk": 2}
    assert shift.persisted == {"naming": 1}
    assert shift.net_resolved == 1  # (2+1) resolved - 2 introduced


def test_taxonomy_shift_pure_net_improvement():
    shift = taxonomy_shift({"naming": 2}, {})
    assert shift.resolved == {"naming": 2}
    assert shift.net_resolved == 2


# ── build_modeller wiring ─────────────────────────────────────────────────────


def test_build_modeller_learning_off_uses_limit_zero():
    calls = {}

    def agent_factory(**kwargs):
        calls.update(kwargs)
        return _Agent(_raw_plan())

    def corpus_loader(settings, *, exclude_catalogs=()):  # must NOT be called
        raise AssertionError("corpus must not load when k=0")

    build_modeller(
        Condition("off", k=0), settings=_Settings(),
        wiring=Wiring(agent_factory=agent_factory, corpus_loader=corpus_loader),
    )
    assert calls["reference_limit_override"] == 0
    assert "reference_loader_override" not in calls


def test_build_modeller_heuristic_producer_uses_heuristic_factory():
    sentinel = object()

    def agent_factory(**kwargs):  # must NOT be called for the heuristic arm
        raise AssertionError("modeller must not be built for a heuristic condition")

    producer = build_modeller(
        Condition("det", producer="heuristic"), settings=_Settings(),
        wiring=Wiring(agent_factory=agent_factory, heuristic_factory=lambda: sentinel),
    )
    assert producer is sentinel


def test_build_modeller_learning_on_threads_exclusions_and_k():
    calls = {}
    loader_args = {}

    def agent_factory(**kwargs):
        calls.update(kwargs)
        return _Agent(_raw_plan())

    def corpus_loader(settings, *, exclude_catalogs=()):
        loader_args["exclude"] = exclude_catalogs
        return "LOADER"

    build_modeller(
        Condition("loo", k=7, exclude_catalogs=("a", "b")), settings=_Settings(),
        wiring=Wiring(agent_factory=agent_factory, corpus_loader=corpus_loader),
    )
    assert loader_args["exclude"] == ("a", "b")
    assert calls["reference_loader_override"] == "LOADER"
    assert calls["reference_limit_override"] == 7


# ── run_condition ─────────────────────────────────────────────────────────────


def _wiring(*, review_plan: ModelingPlan | None):
    reviewer = _Reviewer(review_plan) if review_plan is not None else None
    return Wiring(
        agent_factory=lambda **kw: _Agent(_raw_plan()),
        corpus_loader=lambda s, *, exclude_catalogs=(): "L",
        reviewer_factory=lambda *, settings: reviewer,
        discover=lambda path: _Payload("cust"),
    )


def test_run_condition_without_review_has_no_reviewed():
    rec = run_condition(
        gold=_gold(), payload=_Payload("cust"), condition=Condition("off", k=0),
        seed=42, settings=_Settings(), wiring=_wiring(review_plan=None),
    )
    assert rec.reviewed is None
    assert rec.shift is None
    assert rec.raw.gold_naming_adherence == 0.0  # 'customer' != 'hub_customer'
    assert rec.seed == 42


def test_run_condition_with_review_records_taxonomy_shift():
    rec = run_condition(
        gold=_gold(), payload=_Payload("cust"), condition=Condition("e2e", k=0, review=True),
        seed=42, settings=_Settings(), wiring=_wiring(review_plan=_reviewed_plan()),
    )
    assert rec.reviewed is not None
    assert rec.reviewer_deployment == "gpt-5.2-fake"
    # reviewer fixed the naming: adherence 0 -> 1 and the NAMING issue is resolved.
    assert rec.raw.gold_naming_adherence == 0.0
    assert rec.reviewed.gold_naming_adherence == 1.0
    assert rec.shift.resolved.get("naming") == 1


# ── run_study + resolution ────────────────────────────────────────────────────


def test_run_study_iterates_systems_conditions_seeds():
    golds = {"X": _gold()}
    records = run_study(
        systems=["X"], conditions=[Condition("off"), Condition("e2e", review=True)],
        seeds=[42, 43], settings=_Settings(), golds=golds, wiring=_wiring(review_plan=_reviewed_plan()),
    )
    assert len(records) == 4  # 1 system x 2 conditions x 2 seeds
    assert {r.condition for r in records} == {"off", "e2e"}
    assert {r.seed for r in records} == {42, 43}


def test_run_study_rejects_duplicate_condition_labels():
    # two arms sharing a label would silently merge in summarise() -> fail loud.
    with pytest.raises(ValueError, match="duplicate condition labels"):
        run_study(
            systems=["X"], conditions=[Condition("on", k=1), Condition("on", k=10)],
            seeds=[42], settings=_Settings(), golds={"X": _gold()},
            wiring=_wiring(review_plan=None),
        )


def test_run_study_unknown_system_raises():
    with pytest.raises(ValueError):
        run_study(systems=["NOPE"], conditions=[Condition("off")], seeds=[42],
                  settings=_Settings(), golds={"X": _gold()}, wiring=_wiring(review_plan=None))


def test_resolve_payload_path_missing_raises():
    with pytest.raises(ValueError):
        resolve_payload_path(GoldModel(system_id="X"))


def test_resolve_payload_path_returns_declared():
    assert resolve_payload_path(_gold()) == "poc/metadata/x_discovery.yaml"


# ── summarise ─────────────────────────────────────────────────────────────────


def test_summarise_aggregates_means_and_shift():
    golds = {"X": _gold()}
    records = run_study(
        systems=["X"], conditions=[Condition("e2e", review=True)], seeds=[42, 43],
        settings=_Settings(), golds=golds, wiring=_wiring(review_plan=_reviewed_plan()),
    )
    summary = summarise(records)
    cell = summary["X/e2e"]
    assert cell["raw"].means["gold_naming_adherence"] == 0.0
    assert cell["reviewed"].means["gold_naming_adherence"] == 1.0
    assert cell["shift"].resolved.get("naming") == 2  # summed over 2 seeds


# ── gold model accepts the new provenance field ───────────────────────────────


def test_gold_model_accepts_discovery_payload():
    g = GoldModel(system_id="X", discovery_payload="p.yaml")
    assert g.discovery_payload == "p.yaml"


def test_gold_model_discovery_payload_optional():
    assert GoldModel(system_id="X").discovery_payload is None
