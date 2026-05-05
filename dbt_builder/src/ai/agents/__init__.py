"""LLM-driven Phase 2 agents that turn discovery payloads into modelling plans.

Sub-modules:

* :mod:`modeller` — :class:`ModellingAgent` that takes a
  :class:`DiscoveryPayload` and returns a :class:`ModelingPlan` proposing
  hubs, links, and satellites.
"""

from __future__ import annotations

from dbt_builder.src.ai.agents.modeller import (
    ModellingAgent,
    ModellingAgentError,
    get_modelling_agent,
)

__all__ = [
    "ModellingAgent",
    "ModellingAgentError",
    "get_modelling_agent",
]
