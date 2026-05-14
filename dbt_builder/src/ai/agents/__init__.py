"""LLM-driven Phase 2 / Phase B agents that turn discovery payloads into modelling plans.

Sub-modules:

* :mod:`modeller` — :class:`ModellingAgent` that takes a
  :class:`DiscoveryPayload` and returns a :class:`ModelingPlan` proposing
  hubs, links, and satellites. Lower-level LLM caller; kept for backward
  compatibility with the Phase 2 tests.
* :mod:`schema_analyzer` — :class:`SchemaAnalyzer`, the Phase B / Step-4
  agent. Pipeline-aware wrapper that filters a bronze snapshot via a
  change-set + skip predicate before delegating to a modeller. The
  preferred entry point for new code.
"""

from __future__ import annotations

from dbt_builder.src.ai.agents.bv_architect import (
    BvArchitect,
    BvArchitectError,
    ProposeBvSatsFn,
)
from dbt_builder.src.ai.agents.modeller import (
    ModellingAgent,
    ModellingAgentError,
    get_modelling_agent,
)
from dbt_builder.src.ai.agents.schema_analyzer import (
    SchemaAnalyzer,
    SchemaAnalyzerError,
    SkipPredicate,
    bronze_table_to_source_table,
)
from dbt_builder.src.ai.agents.yaml_generator import (
    YamlBundle,
    YamlFile,
    YamlGenerator,
)

__all__ = [
    "BvArchitect",
    "BvArchitectError",
    "ModellingAgent",
    "ModellingAgentError",
    "ProposeBvSatsFn",
    "SchemaAnalyzer",
    "SchemaAnalyzerError",
    "SkipPredicate",
    "YamlBundle",
    "YamlFile",
    "YamlGenerator",
    "bronze_table_to_source_table",
    "get_modelling_agent",
]
