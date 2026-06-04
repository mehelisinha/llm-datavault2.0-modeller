"""Unit tests for the BV-sat pattern catalogue + detector.

The detector is deterministic and is the floor of the BV-sat pipeline:
zero matches here means zero BV sats, regardless of LLM availability.
These tests pin the catalogue's expected matches so adding a new
pattern can't silently regress existing ones.
"""

from __future__ import annotations

from dbt_builder.src.ai.agents.bv_sat_patterns import (
    PATTERNS,
    detect_bv_candidates,
)
from dbt_builder.src.ai.contracts.bv import BvSatClassification
from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    HubDecision,
    ModelingPlan,
    SatelliteDecision,
)


def _hub(name: str, source_table: str | None = None) -> HubDecision:
    src = source_table or name.removeprefix("hub_")
    return HubDecision(
        name=name,
        business_keys=("mrid",),
        source_table=src,
        hash_key=f"HK_{src.upper()}",
        confidence=DecisionConfidence.HIGH,
        rationale="t",
    )


def _sat(name: str, hub: str, source: str, payload: tuple[str, ...]) -> SatelliteDecision:
    return SatelliteDecision(
        name=name,
        source_table=source,
        parent_hub=hub,
        hash_key=f"HK_{hub.removeprefix('hub_').upper()}",
        hashdiff=f"HASHDIFF_{name.upper()}",
        payload=payload,
        confidence=DecisionConfidence.MEDIUM,
        rationale="t",
    )


def _plan(*, hubs=(), sats=()) -> ModelingPlan:
    return ModelingPlan(system_id="iec_cim", hubs=hubs, satellites=sats)


# ── catalogue invariants ────────────────────────────────────────────────────


def test_pattern_keys_are_unique_and_snake_case() -> None:
    keys = [p.key for p in PATTERNS]
    assert len(keys) == len(set(keys)), "duplicate pattern keys"
    for key in keys:
        assert key == key.lower(), f"pattern key not lowercase: {key}"
        assert " " not in key


def test_every_pattern_template_uses_col_placeholder() -> None:
    for pattern in PATTERNS:
        assert "{col}" in pattern.derivation_template
        assert "{col}" in pattern.rationale_template
        assert pattern.output_columns_template, "must emit at least one column"


# ── detection ──────────────────────────────────────────────────────────────


def test_voltage_tier_pattern_matches_voltage_kv_column() -> None:
    hub = _hub("hub_terminal")
    sat = _sat("sat_terminal_details", "hub_terminal", "terminal", ("voltage_kv", "name"))
    cands = detect_bv_candidates(_plan(hubs=(hub,), sats=(sat,)))
    assert len(cands) == 1
    cand = cands[0]
    assert cand.pattern_key == "voltage_tier"
    assert cand.parent_hub == "hub_terminal"
    assert cand.matched_column == "voltage_kv"
    assert cand.source_models == ("stg_terminal",)
    assert cand.name == "bv_sat_terminal_voltage_tier"
    assert cand.classification is BvSatClassification.CLASSIFICATION


def test_no_candidates_when_no_payload_matches_any_pattern() -> None:
    hub = _hub("hub_terminal")
    sat = _sat("sat_terminal_details", "hub_terminal", "terminal", ("name", "label"))
    assert detect_bv_candidates(_plan(hubs=(hub,), sats=(sat,))) == ()


def test_pattern_is_deduped_per_hub_even_with_two_matching_columns() -> None:
    hub = _hub("hub_terminal")
    sat = _sat(
        "sat_terminal_details",
        "hub_terminal",
        "terminal",
        ("voltage", "nominal_voltage"),  # both match voltage_tier
    )
    cands = detect_bv_candidates(_plan(hubs=(hub,), sats=(sat,)))
    # Exactly one voltage_tier candidate per hub.
    voltage_cands = [c for c in cands if c.pattern_key == "voltage_tier"]
    assert len(voltage_cands) == 1


def test_hub_without_satellites_produces_no_candidates() -> None:
    hub = _hub("hub_terminal")
    assert detect_bv_candidates(_plan(hubs=(hub,))) == ()


def test_candidate_carries_starter_sql_and_output_columns() -> None:
    hub = _hub("hub_terminal")
    sat = _sat("sat_terminal_details", "hub_terminal", "terminal", ("voltage_kv",))
    cand = detect_bv_candidates(_plan(hubs=(hub,), sats=(sat,)))[0]
    assert "voltage_kv" in cand.derivation_sql
    assert cand.output_columns == ("voltage_tier",)
