"""Unit tests for :class:`Descriptor`.

The descriptor's contract: rewrite ``description`` / ``rationale`` /
``notes`` values only, leave everything else byte-identical. Any
violation must trigger a fallback to the original document so a
mis-behaving LLM never silently corrupts the rendered metadata.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from dbt_builder.src.ai.agents.descriptor import Descriptor
from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    HubDecision,
    ModelingPlan,
)
from dbt_builder.src.ai.contracts.payloads import SourceSystem


# ── stub OpenAI client (mirrors test_bv_sat_proposer.py) ───────────────────


class _StubMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _StubChoice:
    def __init__(self, content: str) -> None:
        self.message = _StubMessage(content)


class _StubResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_StubChoice(content)]


class _StubCompletions:
    def __init__(self, payload: str | Exception) -> None:
        self._payload = payload

    def create(self, **kwargs: Any) -> _StubResponse:
        if isinstance(self._payload, Exception):
            raise self._payload
        return _StubResponse(self._payload)


class _StubChat:
    def __init__(self, payload: str | Exception) -> None:
        self.completions = _StubCompletions(payload)


class _StubClient:
    def __init__(self, payload: str | Exception) -> None:
        self.chat = _StubChat(payload)


class _StubSettings:
    pass


# ── fixtures ────────────────────────────────────────────────────────────────


_DOC: dict[str, Any] = {
    "version": 3,
    "system": {"system_id": "iec_cim", "system_name": "IEC CIM"},
    "hubs": [
        {
            "name": "hub_terminal",
            "description": "PLACEHOLDER",
            "business_keys": ["mrid"],
            "meta": {"dv_type": "hub", "load_frequency": "daily"},
        }
    ],
    "satellites": [
        {
            "name": "sat_terminal_details",
            "description": "PLACEHOLDER",
            "parent_hub": "hub_terminal",
            "payload": ["voltage_kv", "name"],
        }
    ],
}


def _system() -> SourceSystem:
    return SourceSystem(system_id="iec_cim", system_name="IEC CIM")


def _plan() -> ModelingPlan:
    return ModelingPlan(
        system_id="iec_cim",
        hubs=(
            HubDecision(
                name="hub_terminal",
                business_keys=("mrid",),
                source_table="terminal",
                hash_key="HK_TERMINAL",
                confidence=DecisionConfidence.HIGH,
                rationale="t",
            ),
        ),
    )


def _descriptor(payload: str | Exception) -> Descriptor:
    return Descriptor(
        client=_StubClient(payload),  # type: ignore[arg-type]
        deployment="gpt-4o-mini",
        settings=_StubSettings(),  # type: ignore[arg-type]
    )


# ── tests ──────────────────────────────────────────────────────────────────


def test_description_only_rewrite_is_accepted() -> None:
    enriched = copy.deepcopy(_DOC)
    enriched["hubs"][0]["description"] = "Conducting equipment terminal endpoints."
    enriched["satellites"][0]["description"] = "Quasi-static terminal attributes."
    descriptor = _descriptor(json.dumps(enriched))
    out = descriptor.enrich(_DOC, plan=_plan(), system=_system(), bv=None)
    assert out["hubs"][0]["description"].startswith("Conducting equipment")
    assert out["satellites"][0]["description"].startswith("Quasi-static")


def test_non_description_change_is_rejected_and_original_is_returned() -> None:
    tampered = copy.deepcopy(_DOC)
    tampered["hubs"][0]["description"] = "fine"
    tampered["hubs"][0]["business_keys"] = ["renamed_key"]  # forbidden
    descriptor = _descriptor(json.dumps(tampered))
    out = descriptor.enrich(_DOC, plan=_plan(), system=_system(), bv=None)
    # Fallback to the original document.
    assert out == _DOC


def test_added_key_is_rejected() -> None:
    tampered = copy.deepcopy(_DOC)
    tampered["hubs"][0]["extra_field"] = "nope"
    descriptor = _descriptor(json.dumps(tampered))
    assert descriptor.enrich(_DOC, plan=_plan(), system=_system(), bv=None) == _DOC


def test_removed_key_is_rejected() -> None:
    tampered = copy.deepcopy(_DOC)
    del tampered["hubs"][0]["business_keys"]
    descriptor = _descriptor(json.dumps(tampered))
    assert descriptor.enrich(_DOC, plan=_plan(), system=_system(), bv=None) == _DOC


def test_invalid_json_falls_back_to_original() -> None:
    descriptor = _descriptor("not-json")
    assert descriptor.enrich(_DOC, plan=_plan(), system=_system(), bv=None) == _DOC


def test_llm_exception_falls_back_to_original() -> None:
    descriptor = _descriptor(RuntimeError("boom"))
    assert descriptor.enrich(_DOC, plan=_plan(), system=_system(), bv=None) == _DOC


def test_non_object_response_falls_back_to_original() -> None:
    descriptor = _descriptor(json.dumps(["wrong", "shape"]))
    assert descriptor.enrich(_DOC, plan=_plan(), system=_system(), bv=None) == _DOC


def test_list_length_change_is_rejected() -> None:
    tampered = copy.deepcopy(_DOC)
    tampered["hubs"][0]["business_keys"] = ["mrid", "extra"]
    descriptor = _descriptor(json.dumps(tampered))
    assert descriptor.enrich(_DOC, plan=_plan(), system=_system(), bv=None) == _DOC
