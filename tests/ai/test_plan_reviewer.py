"""Tests for the LLM plan reviewer (offline, hermetic).

Verifies the two-model review layer improves a valid reply and, crucially,
falls back to the original plan on every failure mode so it can never break
the pipeline.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.ai

from dbt_builder.src.ai.agents.plan_reviewer import (  # noqa: E402
    PlanReviewer,
    _class_collapsed,
    _system_prompt,
)
from dbt_builder.src.ai.contracts.decisions import ModelingPlan  # noqa: E402

from .test_modeller import _FakeClient, _payload, _valid_plan_json  # noqa: E402


def _orig_plan() -> ModelingPlan:
    return ModelingPlan.model_validate(json.loads(_valid_plan_json()))


def _multi_hub_plan_json(n_hubs: int) -> str:
    """A valid plan with ``n_hubs`` independent hubs (no links/sats)."""
    return json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": f"hub_{i}",
                    "source_table": "conducting_equipment",
                    "business_keys": ["mrid"],
                    "hash_key": f"HK_{i}",
                }
                for i in range(n_hubs)
            ],
            "links": [],
            "satellites": [],
        }
    )


def _reviewer(responses, deployment: str = "gpt-4o", *, chunk_size: int = 0, parallelism: int = 1):
    client = _FakeClient(responses)
    rv = PlanReviewer(
        client=client,  # type: ignore[arg-type]
        deployment=deployment,
        # parallelism defaults to 1 so order-sensitive chunk tests stay
        # deterministic; pass parallelism=0 to exercise the concurrent path.
        settings=SimpleNamespace(  # type: ignore[arg-type]
            llm_seed=42,
            plan_review_chunk_size=chunk_size,
            plan_review_parallelism=parallelism,
        ),
        max_tokens=4096,
    )
    return rv, client.chat.completions


def _plan_json_for_hubs(hubs) -> str:
    """A valid plan reply echoing exactly the given hubs (no links/sats)."""
    return json.dumps(
        {
            "system_id": "iec_cim",
            "hubs": [
                {
                    "name": h.name,
                    "source_table": h.source_table,
                    "business_keys": list(h.business_keys),
                    "hash_key": h.hash_key,
                }
                for h in hubs
            ],
            "links": [],
            "satellites": [],
        }
    )


def _hub_chunks(plan: ModelingPlan, chunk_size: int):
    """Reproduce the reviewer's hub partitioning so tests derive, not hardcode."""
    hubs = sorted(plan.hubs, key=lambda h: h.name.lower())
    return [hubs[i : i + chunk_size] for i in range(0, len(hubs), chunk_size)]


def test_review_returns_corrected_plan() -> None:
    rv, calls = _reviewer([_valid_plan_json()])
    reviewed = rv.review(_orig_plan(), _payload())
    assert isinstance(reviewed, ModelingPlan)
    assert reviewed.entity_count == 2
    assert len(calls.calls) == 1


def test_invalid_json_falls_back_to_original() -> None:
    orig = _orig_plan()
    rv, _ = _reviewer(["not valid json at all"])
    reviewed = rv.review(orig, _payload())
    assert reviewed == orig  # identity fallback


def test_dropping_all_hubs_falls_back_to_original() -> None:
    orig = _orig_plan()
    emptied = json.dumps({"system_id": "iec_cim", "hubs": [], "links": [], "satellites": []})
    rv, _ = _reviewer([emptied])
    reviewed = rv.review(orig, _payload())
    assert reviewed == orig  # guard keeps the original when review empties hubs


def test_catastrophic_shrink_falls_back_to_original() -> None:
    # Reproduces the 107-table regression: the reviewer collapses a 6-hub plan
    # down to one. The shrink guard must keep the original plan instead.
    orig = ModelingPlan.model_validate(json.loads(_multi_hub_plan_json(6)))
    collapsed = _multi_hub_plan_json(1)
    rv, _ = _reviewer([collapsed])
    reviewed = rv.review(orig, _payload())
    assert reviewed == orig  # collapse rejected


def test_legitimate_trim_of_one_entity_is_accepted() -> None:
    # Dropping a single stray hub is a normal refine, not a collapse, so the
    # reviewed plan is accepted rather than discarded.
    orig = ModelingPlan.model_validate(json.loads(_multi_hub_plan_json(5)))
    trimmed = _multi_hub_plan_json(4)
    rv, _ = _reviewer([trimmed])
    reviewed = rv.review(orig, _payload())
    assert len(reviewed.hubs) == 4  # accepted, not rolled back to 5


def test_large_plan_is_reviewed_in_chunks_preserving_all_hubs() -> None:
    # 4 hubs, chunk size 2 → two chunks, one reviewer call each. Each chunk
    # echoes its own hubs, so the merged plan keeps every hub (no collapse).
    orig = ModelingPlan.model_validate(json.loads(_multi_hub_plan_json(4)))
    chunks = _hub_chunks(orig, 2)
    responses = [_plan_json_for_hubs(c) for c in chunks]
    rv, calls = _reviewer(responses, chunk_size=2)
    reviewed = rv.review(orig, _payload())
    assert len(calls.calls) == len(chunks)  # one call per chunk, not one whole-plan call
    assert {h.name for h in reviewed.hubs} == {h.name for h in orig.hubs}


def test_chunked_review_runs_in_parallel_preserving_all_hubs() -> None:
    # With parallelism enabled (0 = one worker per chunk), each chunk still gets
    # reviewed and every hub survives the merge. Echo responses make the union
    # order-insensitive, so the assertion holds regardless of completion order.
    orig = ModelingPlan.model_validate(json.loads(_multi_hub_plan_json(6)))
    chunks = _hub_chunks(orig, 2)
    responses = [_plan_json_for_hubs(c) for c in chunks]
    rv, calls = _reviewer(responses, chunk_size=2, parallelism=0)
    reviewed = rv.review(orig, _payload())
    assert len(calls.calls) == len(chunks)  # one call per chunk
    assert {h.name for h in reviewed.hubs} == {h.name for h in orig.hubs}


def test_chunked_review_falls_back_per_chunk_on_collapse() -> None:
    # If one chunk collapses (returns no hubs), only that chunk falls back to its
    # original — the other chunk's refinement still applies and no hub is lost.
    orig = ModelingPlan.model_validate(json.loads(_multi_hub_plan_json(4)))
    chunks = _hub_chunks(orig, 2)
    emptied = json.dumps({"system_id": "iec_cim", "hubs": [], "links": [], "satellites": []})
    responses = [emptied, _plan_json_for_hubs(chunks[1])]
    rv, _ = _reviewer(responses, chunk_size=2)
    reviewed = rv.review(orig, _payload())
    assert {h.name for h in reviewed.hubs} == {h.name for h in orig.hubs}


@pytest.mark.parametrize(
    ("original", "reviewed", "collapsed"),
    [
        (24, 6, True),  # the live 107-run collapse
        (7, 4, True),  # below 70%
        (7, 5, False),  # 71% kept — a refine
        (5, 4, False),  # lost one — within the absolute floor
        (3, 2, False),  # small plan, lost one
        (4, 4, False),  # unchanged
        (4, 6, False),  # grew
        (1, 0, True),  # emptied a non-empty class
        (0, 0, False),  # nothing to lose
    ],
)
def test_class_collapsed_thresholds(original: int, reviewed: int, collapsed: bool) -> None:
    assert _class_collapsed(original, reviewed) is collapsed


def test_system_id_is_forced_from_original() -> None:
    rv, _ = _reviewer([_valid_plan_json(system_id="WRONG")])
    reviewed = rv.review(_orig_plan(), _payload())
    assert reviewed.system_id == "iec_cim"


def test_gpt5_reviewer_uses_completion_tokens_and_temperature_one() -> None:
    rv, calls = _reviewer([_valid_plan_json()], deployment="gpt-5.2")
    rv.review(_orig_plan(), _payload())
    kwargs = calls.calls[0]
    assert kwargs["temperature"] == 1.0
    assert "max_completion_tokens" in kwargs
    assert "max_tokens" not in kwargs


def test_system_prompt_has_rules_and_output_contract() -> None:
    sp = _system_prompt()
    assert "Data Vault 2.0 reviewer" in sp
    assert "STRICT JSON" in sp
    assert "system_id" in sp


def test_factory_returns_none_when_disabled() -> None:
    from dbt_builder.src.ai.agents.plan_reviewer import get_plan_reviewer
    from dbt_builder.src.ai.settings import AISettings

    cfg = AISettings(plan_review_enabled=False)  # type: ignore[call-arg]
    assert get_plan_reviewer(settings=cfg) is None
