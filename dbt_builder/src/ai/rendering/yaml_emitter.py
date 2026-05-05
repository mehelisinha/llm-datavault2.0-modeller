"""Render :class:`ModelingPlan` objects into the existing DWA YAML format.

The Phase 2 agent produces a strongly-typed :class:`ModelingPlan`. The rest
of the DWA pipeline already speaks YAML in the shape of
``poc/metadata/iec_cim_metadata.yaml`` (consumed by ``MetadataReader`` ->
``DVGenerator``). This emitter is a pure, deterministic translation between
the two so:

* Phase 2 output drops straight into the existing renderer with no code
  changes downstream.
* The emitter is fully testable offline (no Azure, no dbt invocation).

Scope
-----
The emitter writes the blocks the modelling agent owns:

* ``system``      — from :class:`SourceSystem` plus a few constants.
* ``hubs``        — one per :class:`HubDecision`.
* ``satellites``  — one per :class:`SatelliteDecision`.
* ``links``       — one per :class:`LinkDecision`.
* ``staging``     — synthesised: one staging entry per source table that
  any hub / satellite references, with hashed_columns derived from the
  hub business keys and satellite payloads.

Out of scope (left to the operator, identical to the hand-written file):
``packages``, ``macros``, ``eff_sats``, ``pit_tables``, ``bridge_tables``,
``dim_tables``, ``fact_tables``, ``bv_sats``. These are stable defaults
or business-vault concerns that don't depend on the source schema.
``packages`` and ``macros`` are emitted as a small default block so the
output is valid as-is.
"""

from __future__ import annotations

from collections.abc import Iterable
from io import StringIO
from pathlib import Path
from typing import Any

import yaml

from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.contracts.payloads import SourceSystem

_DEFAULT_PACKAGES: list[dict[str, Any]] = [
    {"package": "dbt-labs/dbt_utils", "version": "1.3.3"},
    {"package": "metaplane/dbt_expectations", "version": "0.10.10"},
    {"package": "Datavault-UK/automate_dv", "version": "0.10.2"},
]

_DEFAULT_MACROS: list[dict[str, Any]] = [
    {
        "name": "generate_schema_name",
        "description": (
            "Generates the schema name by overwriting the AutomateDV default behavior."
        ),
    },
]


def render_plan(
    plan: ModelingPlan,
    system: SourceSystem,
    *,
    load_frequency: str = "daily",
) -> str:
    """Return the YAML string for ``plan`` + ``system``.

    ``system`` is supplied separately because :class:`ModelingPlan` only
    carries ``system_id``; the full :class:`SourceSystem` (with catalog /
    schema / record_source) lives on the :class:`DiscoveryPayload` that
    fed the agent and is the caller's responsibility to thread through.
    """
    if plan.system_id != system.system_id:
        raise ValueError(
            f"Plan system_id '{plan.system_id}' does not match "
            f"SourceSystem.system_id '{system.system_id}'."
        )
    document = _build_document(plan, system, load_frequency=load_frequency)
    buf = StringIO()
    yaml.safe_dump(
        document,
        buf,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return buf.getvalue()


def write_plan(
    plan: ModelingPlan,
    system: SourceSystem,
    output_path: str | Path,
    *,
    load_frequency: str = "daily",
) -> Path:
    """Render and write the YAML to ``output_path``; return the path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_plan(plan, system, load_frequency=load_frequency), encoding="utf-8")
    return path


# ====================================================================== internals


def _build_document(
    plan: ModelingPlan,
    system: SourceSystem,
    *,
    load_frequency: str,
) -> dict[str, Any]:
    return {
        "system": _system_block(system, load_frequency=load_frequency),
        "packages": list(_DEFAULT_PACKAGES),
        "macros": list(_DEFAULT_MACROS),
        "hubs": [_hub_block(h) for h in plan.hubs],
        "satellites": [_sat_block(s) for s in plan.satellites],
        "links": [_link_block(ln) for ln in plan.links],
        "staging": _staging_blocks(plan),
    }


def _system_block(system: SourceSystem, *, load_frequency: str) -> dict[str, Any]:
    block: dict[str, Any] = {
        "system_id": system.system_id,
        "system_name": system.system_name,
        "source_type": system.source_type,
    }
    if system.catalog:
        block["catalog"] = system.catalog
    if system.schema_name:
        block["schema"] = system.schema_name
    block["load_frequency"] = load_frequency
    block["record_source"] = system.record_source or system.system_id
    block["record_source_column"] = "RECORD_SOURCE"
    block["default_ldts"] = "LOAD_DATE"
    return block


def _staging_model_name(source_table: str) -> str:
    return f"stg_{source_table}"


def _hub_block(hub: HubDecision) -> dict[str, Any]:
    block: dict[str, Any] = {
        "name": hub.name,
        "source_table": hub.source_table,
        "staging_model": _staging_model_name(hub.source_table),
    }
    # Single business key -> scalar (matches the hand-written file's style);
    # composite keys -> list. The downstream reader accepts both.
    if len(hub.business_keys) == 1:
        block["business_key"] = hub.business_keys[0]
    else:
        block["business_key"] = list(hub.business_keys)
    block["hash_key"] = hub.hash_key
    return block


def _sat_block(sat: SatelliteDecision) -> dict[str, Any]:
    block: dict[str, Any] = {
        "name": sat.name,
        "parent_hub": sat.parent_hub,
        "source_model": _staging_model_name(sat.source_table),
        "hash_key": sat.hash_key,
        "hashdiff": sat.hashdiff,
        "effective_from": sat.effective_from or "EFFECTIVE_FROM",
        "payload": list(sat.payload),
    }
    return block


def _link_block(link: LinkDecision) -> dict[str, Any]:
    return {
        "name": link.name,
        "source_model": _staging_model_name(link.source_table),
        "hash_key": link.hash_key,
        "fk_columns": list(link.fk_columns),
    }


def _staging_blocks(plan: ModelingPlan) -> list[dict[str, Any]]:
    """Synthesise one staging entry per source table referenced by the plan.

    For each source table we collect:

    * ``hashed_columns`` containing every hub hash_key (with its business
      keys) plus every satellite hashdiff (with its payload).

    Order is deterministic: hubs first (by hub name), then satellites
    (by satellite name) within each table. Tables themselves are emitted
    in first-seen order across hubs -> satellites -> links so the file
    diffs cleanly across runs that don't change the model.
    """
    table_order: list[str] = []
    hubs_by_table: dict[str, list[HubDecision]] = {}
    sats_by_table: dict[str, list[SatelliteDecision]] = {}

    def _track(table: str) -> None:
        if table not in table_order:
            table_order.append(table)

    for hub in plan.hubs:
        _track(hub.source_table)
        hubs_by_table.setdefault(hub.source_table, []).append(hub)
    for sat in plan.satellites:
        _track(sat.source_table)
        sats_by_table.setdefault(sat.source_table, []).append(sat)
    for link in plan.links:
        _track(link.source_table)

    blocks: list[dict[str, Any]] = []
    for table in table_order:
        hashed = _hashed_columns(
            hubs=sorted(hubs_by_table.get(table, ()), key=lambda h: h.name),
            sats=sorted(sats_by_table.get(table, ()), key=lambda s: s.name),
        )
        block: dict[str, Any] = {
            "name": _staging_model_name(table),
            "source_table": table,
            "derived_columns": {
                "RECORD_SOURCE": "record_source",
                "LOAD_DATE": "load_dts",
                "EFFECTIVE_FROM": "load_dts",
                "CDC_FLAG": "cdc_flag",
            },
        }
        if hashed:
            block["hashed_columns"] = hashed
        blocks.append(block)
    return blocks


def _hashed_columns(
    *,
    hubs: Iterable[HubDecision],
    sats: Iterable[SatelliteDecision],
) -> dict[str, Any]:
    columns: dict[str, Any] = {}
    for hub in hubs:
        # Hub hash key -> ordered list of business-key columns.
        columns[hub.hash_key] = list(hub.business_keys)
    for sat in sats:
        columns[sat.hashdiff] = {
            "is_hashdiff": True,
            "columns": list(sat.payload),
        }
    return columns
