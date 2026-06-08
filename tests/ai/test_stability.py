"""Determinism / idempotency tests for the LLM agents (offline).

These guard the two safety contracts of the Phase B stability work:

1. When ``llm_seed >= 0``, every chat-completion call carries a ``seed``
   kwarg whose value is reproducible from ``(base_seed, sample_idx)``.
2. Running ``ModellingAgent.propose`` twice over the same canned
   responses produces a plan with the same ``_fingerprint`` and the
   same ``model_dump()`` (no hidden order-dependence in voting).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ai

from dbt_builder.src.ai.agents.descriptor import Descriptor
from dbt_builder.src.ai.agents.modeller import ModellingAgent, _fingerprint
from dbt_builder.src.ai.settings import AISettings

from .test_modeller import _FakeClient, _payload, _valid_plan_json


def _settings(*, seed: int = 42) -> AISettings:
    # AISettings requires endpoint+key; supply harmless dummies.
    return AISettings(
        azure_openai_endpoint="https://example.invalid",
        azure_openai_api_key="sk-test",  # pyright: ignore[reportArgumentType]
        llm_seed=seed,
    )


# ── modeller seed plumbing ────────────────────────────────────────────────


def test_modeller_passes_seed_per_sample() -> None:
    client = _FakeClient([_valid_plan_json(), _valid_plan_json(), _valid_plan_json()])
    agent = ModellingAgent(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o",
        samples=3,
        max_tokens=512,
        seed=42,
    )
    agent.propose(_payload())
    calls = client.chat.completions.calls
    assert len(calls) == 3
    seeds = [c["seed"] for c in calls]
    # base + sample_idx for idx in 0..2 → 42, 43, 44
    assert seeds == [42, 43, 44]


def test_modeller_omits_seed_when_disabled() -> None:
    client = _FakeClient([_valid_plan_json()])
    agent = ModellingAgent(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o",
        samples=1,
        max_tokens=512,
        seed=None,
    )
    agent.propose(_payload())
    assert "seed" not in client.chat.completions.calls[0]


# ── two-run idempotency ───────────────────────────────────────────────────


def test_modeller_propose_is_idempotent_across_runs() -> None:
    """Same canned LLM responses → byte-identical ModelingPlan."""
    responses_a = [_valid_plan_json(), _valid_plan_json(), _valid_plan_json()]
    responses_b = list(responses_a)

    agent_a = ModellingAgent(
        client=_FakeClient(responses_a),  # type: ignore[arg-type]
        deployment="gpt-4o",
        samples=3,
        max_tokens=512,
        seed=42,
    )
    agent_b = ModellingAgent(
        client=_FakeClient(responses_b),  # type: ignore[arg-type]
        deployment="gpt-4o",
        samples=3,
        max_tokens=512,
        seed=42,
    )

    plan_a = agent_a.propose(_payload())
    plan_b = agent_b.propose(_payload())

    assert _fingerprint(plan_a) == _fingerprint(plan_b)
    assert plan_a.model_dump() == plan_b.model_dump()


# ── descriptor seed plumbing ──────────────────────────────────────────────


def test_descriptor_passes_seed_from_settings() -> None:
    settings = _settings(seed=7)
    client = _FakeClient(['{"document":{}}'])
    descriptor = Descriptor(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o",
        settings=settings,
        max_tokens=512,
    )
    # Touch the call path directly — `enrich` requires a full document
    # graph, but `_call` exercises the kwargs builder.
    descriptor._call("ping")  # type: ignore[attr-defined]
    assert client.chat.completions.calls[0]["seed"] == 7


def test_descriptor_omits_seed_when_disabled() -> None:
    settings = _settings(seed=-1)
    client = _FakeClient(['{"document":{}}'])
    descriptor = Descriptor(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-4o",
        settings=settings,
        max_tokens=512,
    )
    descriptor._call("ping")  # type: ignore[attr-defined]
    assert "seed" not in client.chat.completions.calls[0]
