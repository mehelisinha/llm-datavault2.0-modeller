"""AI-layer Pydantic contracts.

These typed models define the **interfaces** between the offline discovery /
profiling code (Phase 1) and the LLM-driven modelling agents (Phase 2). Keeping
inputs and outputs strictly typed lets us:

* exchange data deterministically between modules and across process boundaries
  (JSON, pickle, files);
* validate LLM output before it touches dbt artefacts;
* version-control schema evolution with explicit field aliases.

Sub-modules:

* :mod:`payloads`   — inputs to the modelling agents (source columns, tables,
                      profiling statistics, full discovery payload).
* :mod:`decisions`  — outputs from the modelling agents (proposed Data Vault 2
                      hubs, links, satellites and their assembled plan).
"""

from __future__ import annotations

from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    EntityKind,
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.contracts.payloads import (
    ColumnProfile,
    DiscoveryPayload,
    InferredType,
    SourceColumn,
    SourceSystem,
    SourceTable,
)

__all__ = [
    "ColumnProfile",
    "DecisionConfidence",
    "DiscoveryPayload",
    "EntityKind",
    "HubDecision",
    "InferredType",
    "LinkDecision",
    "ModelingPlan",
    "SatelliteDecision",
    "SourceColumn",
    "SourceSystem",
    "SourceTable",
]
