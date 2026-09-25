"""Grounding (hallucination) metric + statistical helpers. Pure, no network."""

from __future__ import annotations

import pytest

from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.contracts.payloads import (
    DiscoveryPayload,
    SourceColumn,
    SourceSystem,
    SourceTable,
)
from dbt_builder.src.ai.evaluation.grounding import check_grounding
from dbt_builder.src.ai.evaluation.stats import (
    bootstrap_ci,
    cohens_kappa,
    idempotency_rate,
    plan_fingerprint,
    self_consistency,
)


def _payload() -> DiscoveryPayload:
    return DiscoveryPayload(
        system=SourceSystem(system_id="s", system_name="S"),
        tables=(
            SourceTable(name="terminals", columns=(
                SourceColumn(name="mrid", raw_dtype="string"),
                SourceColumn(name="name", raw_dtype="string"),
                SourceColumn(name="phases", raw_dtype="string"),
            )),
        ),
    )


def _hub(table="terminals", keys=("mrid",)):
    return HubDecision(name="hub_terminal", source_table=table, business_keys=keys,
                       hash_key="HK_TERMINAL")


def _sat(table="terminals", payload=("name",)):
    return SatelliteDecision(name="sat_terminal", source_table=table, parent_hub="hub_terminal",
                             hash_key="HK_TERMINAL", hashdiff="HD_TERMINAL", payload=payload)


# ── grounding / hallucination ────────────────────────────────────────────────


def test_fully_grounded_plan_has_zero_hallucination():
    plan = ModelingPlan(system_id="s", hubs=(_hub(),), satellites=(_sat(),))
    rep = check_grounding(plan, _payload())
    assert rep.hallucination_rate == 0.0
    assert rep.grounding_rate == 1.0
    assert rep.total_references == 4  # hub table+key, sat table+1 payload column


def test_invented_table_is_flagged():
    plan = ModelingPlan(system_id="s", hubs=(_hub(table="ghost_table"),))
    rep = check_grounding(plan, _payload())
    assert rep.fabricated_tables and "ghost_table" in rep.fabricated_tables[0]
    assert rep.hallucination_rate > 0


def test_invented_business_key_is_flagged():
    plan = ModelingPlan(system_id="s", hubs=(_hub(keys=("not_a_column",)),))
    rep = check_grounding(plan, _payload())
    assert any("not_a_column" in c for c in rep.fabricated_columns)


def test_invented_payload_column_is_flagged():
    plan = ModelingPlan(system_id="s", hubs=(_hub(),),
                        satellites=(_sat(payload=("name", "invented_col")),))
    rep = check_grounding(plan, _payload())
    assert any("invented_col" in c for c in rep.fabricated_columns)
    assert rep.fabricated_references == 1


def test_columns_on_an_invented_table_count_as_fabricated():
    plan = ModelingPlan(system_id="s", hubs=(_hub(table="ghost", keys=("a", "b")),))
    rep = check_grounding(plan, _payload())
    # the table plus both of its unverifiable columns
    assert rep.fabricated_references == 3


def test_grounding_is_case_insensitive():
    plan = ModelingPlan(system_id="s", hubs=(_hub(table="TERMINALS", keys=("MRID",)),))
    assert check_grounding(plan, _payload()).hallucination_rate == 0.0


def test_link_source_table_is_checked():
    plan = ModelingPlan(
        system_id="s", hubs=(_hub(),),
        links=(LinkDecision(name="link_x", source_table="ghost", hash_key="HK_X",
                            fk_columns=("HK_A", "HK_B")),),
    )
    rep = check_grounding(plan, _payload())
    assert any("ghost" in t for t in rep.fabricated_tables)


# ── Cohen's kappa ────────────────────────────────────────────────────────────


def test_kappa_perfect_agreement():
    assert cohens_kappa(["a", "b", "c"], ["a", "b", "c"]) == 1.0


def test_kappa_is_lower_than_accuracy_when_one_class_dominates():
    # 9/10 agreement, but almost everything is "a" -> chance agreement is high.
    a = ["a"] * 9 + ["b"]
    b = ["a"] * 10
    k = cohens_kappa(a, b)
    assert k < 0.9  # accuracy would say 0.9; kappa corrects for chance
    assert k <= 0.0 or k < 0.5


def test_kappa_single_identical_label_is_one():
    assert cohens_kappa(["x", "x"], ["x", "x"]) == 1.0


def test_kappa_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        cohens_kappa(["a"], ["a", "b"])


# ── bootstrap CI ─────────────────────────────────────────────────────────────


def test_bootstrap_ci_brackets_the_mean():
    vals = [0.90, 0.92, 0.88, 0.91, 0.89]
    lo, hi = bootstrap_ci(vals, seed=1)
    mean = sum(vals) / len(vals)
    assert lo <= mean <= hi


def test_bootstrap_ci_is_deterministic_for_a_seed():
    vals = [1.0, 2.0, 3.0, 4.0]
    assert bootstrap_ci(vals, seed=7) == bootstrap_ci(vals, seed=7)


def test_bootstrap_ci_single_value_collapses():
    assert bootstrap_ci([0.75]) == (0.75, 0.75)


# ── self-consistency / idempotency ───────────────────────────────────────────


def _plan(hub_name: str) -> ModelingPlan:
    return ModelingPlan(system_id="s", hubs=(
        HubDecision(name=hub_name, source_table="terminals", business_keys=("mrid",),
                    hash_key="HK_T"),))


def test_self_consistency_all_identical():
    plans = [_plan("hub_terminal") for _ in range(4)]
    assert self_consistency(plans) == 1.0
    assert idempotency_rate(plans) == 1.0


def test_self_consistency_majority():
    plans = [_plan("hub_a"), _plan("hub_a"), _plan("hub_a"), _plan("hub_b")]
    assert self_consistency(plans) == 0.75


def test_fingerprint_ignores_ordering():
    h1 = HubDecision(name="hub_a", source_table="t", business_keys=("k",), hash_key="HK_A")
    h2 = HubDecision(name="hub_b", source_table="t", business_keys=("k",), hash_key="HK_B")
    assert plan_fingerprint(ModelingPlan(system_id="s", hubs=(h1, h2))) == \
           plan_fingerprint(ModelingPlan(system_id="s", hubs=(h2, h1)))


def test_idempotency_stricter_than_consistency():
    # Same entity names (same fingerprint) but a different business key.
    a = ModelingPlan(system_id="s", hubs=(HubDecision(
        name="hub_t", source_table="terminals", business_keys=("mrid",), hash_key="HK_T"),))
    b = ModelingPlan(system_id="s", hubs=(HubDecision(
        name="hub_t", source_table="terminals", business_keys=("name",), hash_key="HK_T"),))
    assert self_consistency([a, b]) == 1.0   # fingerprints match
    assert idempotency_rate([a, b]) == 0.5   # full plans do not
