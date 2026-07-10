"""Phase 3: feedback-learning retrieval wired into the modelling agent."""

from __future__ import annotations

from dbt_builder.src.ai.agents.modeller import ModellingAgent, _build_user_prompt
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
from dbt_builder.src.ai.reference import ReferenceLoader
from dbt_builder.src.ai.store.corpus import plan_to_example_rows


def _plan() -> ModelingPlan:
    return ModelingPlan(
        system_id="iec",
        hubs=(
            HubDecision(
                name="hub_terminal",
                source_table="terminals",
                business_keys=("mrid",),
                hash_key="HK_TERMINAL",
            ),
            HubDecision(
                name="hub_equipment",
                source_table="equipment",
                business_keys=("mrid",),
                hash_key="HK_EQUIPMENT",
            ),
        ),
        links=(
            LinkDecision(
                name="link_terminal_equipment",
                source_table="terminals",
                hash_key="HK_TERMINAL_EQUIPMENT",
                fk_columns=("HK_TERMINAL", "HK_EQUIPMENT"),
            ),
        ),
        satellites=(
            SatelliteDecision(
                name="sat_terminal_details",
                source_table="terminals",
                parent_hub="hub_terminal",
                hash_key="HK_TERMINAL",
                hashdiff="HD_TERMINAL",
                payload=("name", "phases"),
            ),
        ),
    )


def _corpus_loader() -> ReferenceLoader:
    rows = plan_to_example_rows(_plan(), catalog_id="iec", plan_id="p1", version=1, approved_by="u")
    return ReferenceLoader.from_corpus_rows(rows)


def _payload(table: str = "terminals") -> DiscoveryPayload:
    return DiscoveryPayload(
        system=SourceSystem(system_id="iec", system_name="IEC"),
        tables=(
            SourceTable(name=table, columns=(SourceColumn(name="mrid", raw_dtype="varchar"),)),
        ),
    )


def _agent(**overrides) -> ModellingAgent:
    kwargs = dict(client=None, deployment="gpt-4o", samples=1)
    kwargs.update(overrides)
    return ModellingAgent(**kwargs)


# ── from_corpus_rows ────────────────────────────────────────────────────────


def test_from_corpus_rows_rebuilds_examples():
    loader = _corpus_loader()
    names = {ex.name for ex in loader.all()}
    assert names == {
        "hub_terminal",
        "hub_equipment",
        "link_terminal_equipment",
        "sat_terminal_details",
    }


def test_from_corpus_rows_examples_are_retrievable():
    loader = _corpus_loader()
    picks = loader.select_relevant("terminals", limit=5)
    assert any(ex.name == "hub_terminal" for ex in picks)


def test_from_corpus_rows_skips_unknown_kind_and_bad_yaml():
    class _Row:
        def __init__(self, kind, source_path, yaml_text):
            self.kind = kind
            self.source_path = source_path
            self.yaml_text = yaml_text

    rows = [
        _Row("hub", "models/raw_vault/hubs/hub_x.yml", "not: [valid"),  # bad yaml
        _Row("bogus", "models/raw_vault/hubs/hub_y.yml", "version: 2\n"),  # bad kind
    ]
    loader = ReferenceLoader.from_corpus_rows(rows)
    assert loader.all() == ()


# ── _reference_block ────────────────────────────────────────────────────────


def test_reference_block_empty_without_loader():
    assert _agent(reference_loader=None, reference_limit=3)._reference_block(_payload()) == ""


def test_reference_block_empty_when_limit_zero():
    agent = _agent(reference_loader=_corpus_loader(), reference_limit=0)
    assert agent._reference_block(_payload()) == ""


def test_reference_block_returns_relevant_examples():
    agent = _agent(reference_loader=_corpus_loader(), reference_limit=2)
    block = agent._reference_block(_payload("terminals"))
    assert "hub_terminal" in block


def test_reference_block_respects_limit():
    agent = _agent(reference_loader=_corpus_loader(), reference_limit=1)
    block = agent._reference_block(_payload("terminals"))
    # exactly one example rendered → exactly one "### Reference" header
    assert block.count("### Reference") == 1


# ── _build_user_prompt prepend ──────────────────────────────────────────────


def test_prompt_unchanged_without_reference_block():
    prompt = _build_user_prompt(_payload())
    assert "APPROVED REFERENCE EXAMPLES" not in prompt


def test_prompt_prepends_reference_block():
    prompt = _build_user_prompt(_payload(), reference_block="### Reference 1: hub_terminal (hub)")
    assert "APPROVED REFERENCE EXAMPLES" in prompt
    assert "hub_terminal" in prompt
    # the source-system JSON still follows
    assert "Source system:" in prompt
    assert prompt.index("APPROVED REFERENCE EXAMPLES") < prompt.index("Source system:")
