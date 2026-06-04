"""Render a full v3-style monolithic metadata YAML from pipeline artifacts.

The v3 format (see ``iec_cim_metadata_v3.yaml``) is a single document that
captures the *entire* pipeline for one source system:

    system · packages · macros
    hubs · satellites · links          (raw vault — from ModelingPlan)
    eff_sats                           (one per link — deterministic)
    staging                            (one per source table — deterministic)
    pit_tables · bridge_tables         (business vault — from BvProposal)
    dim_tables · fact_tables           (consumption layer — deterministic)
    bv_sats                            (business vault sats — from BvProposal)
    databricks_optimization            (global defaults — constant)

All ``databricks_config`` blocks are derived from
:mod:`~dbt_builder.src.ai.rendering.databricks_defaults` — no literals here.
All naming derives from the contracts; no hardcoded names.

Deterministic outputs
---------------------
* ``eff_sat`` name  : ``eff_sat_{link_name_without_lnk_prefix}``
* ``dim`` name      : ``dim_{hub.source_table}``
* ``fact`` name     : ``fct_{bridge_name_without_brg_or_br_prefix}``
* ``bv_sat hashdiff``: ``HASHDIFF_BV_{bv_sat_name_without_bv_sat_prefix_upper}``
"""

from __future__ import annotations

from collections.abc import Iterable
from io import StringIO
from typing import Any

import yaml

from dbt_builder.src.ai.contracts.bv import BridgeTable, BvProposal, BvSatellite, PitTable
from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.contracts.payloads import SourceSystem
from dbt_builder.src.ai.rendering import databricks_defaults as db
from dbt_builder.src.ai.rendering.yaml_emitter import (
    _DEFAULT_MACROS,
    _DEFAULT_PACKAGES,
    _hashed_columns,
    _staging_model_name,
    _system_block,
)

# ── Naming helpers ────────────────────────────────────────────────────────────

_LNK_PREFIX = "lnk_"
_BRG_PREFIXES = ("brg_", "br_")
_BV_SAT_PREFIX = "bv_sat_"
_EFFECTIVE_FROM = "EFFECTIVE_FROM"
_START_DATE = "START_DATE"
_END_DATE = "END_DATE"
_LOAD_DATE = "LOAD_DATE"
_DBTVAULT_RANK_COL = "DBTVAULT_RANK"
_RANK_ORDER_BY = "load_dts"


def _eff_sat_name(link_name: str) -> str:
    suffix = link_name[len(_LNK_PREFIX):] if link_name.startswith(_LNK_PREFIX) else link_name
    return f"eff_sat_{suffix}"


def _dim_name(hub: HubDecision) -> str:
    return f"dim_{hub.source_table}"


def _fact_name(bridge_name: str) -> str:
    for prefix in _BRG_PREFIXES:
        if bridge_name.startswith(prefix):
            return f"fct_{bridge_name[len(prefix):]}"
    return f"fct_{bridge_name}"


def _bv_hashdiff(bv_sat_name: str) -> str:
    suffix = (
        bv_sat_name[len(_BV_SAT_PREFIX):]
        if bv_sat_name.startswith(_BV_SAT_PREFIX)
        else bv_sat_name
    )
    return f"HASHDIFF_BV_{suffix.upper()}"


# ── Index builders ────────────────────────────────────────────────────────────


def _hub_index(plan: ModelingPlan) -> dict[str, HubDecision]:
    return {h.name: h for h in plan.hubs}


def _sats_by_hub(plan: ModelingPlan) -> dict[str, list[SatelliteDecision]]:
    index: dict[str, list[SatelliteDecision]] = {}
    for sat in plan.satellites:
        index.setdefault(sat.parent_hub, []).append(sat)
    return index


def _link_index(plan: ModelingPlan) -> dict[str, LinkDecision]:
    return {ln.name: ln for ln in plan.links}


def _pit_index(bv: BvProposal | None) -> dict[str, PitTable]:
    if bv is None:
        return {}
    return {pit.parent_hub: pit for pit in bv.pit_tables}


# ── Section builders ──────────────────────────────────────────────────────────


def _hub_block(hub: HubDecision) -> dict[str, Any]:
    bk: Any = hub.business_keys[0] if len(hub.business_keys) == 1 else list(hub.business_keys)
    return {
        "name": hub.name,
        "source_table": hub.source_table,
        "staging_model": _staging_model_name(hub.source_table),
        "business_key": bk,
        "hash_key": hub.hash_key,
        "databricks_config": db.hub_config(hub.hash_key),
    }


def _sat_block(sat: SatelliteDecision) -> dict[str, Any]:
    # Subgroup-aware default description so reviewers can instantly tell
    # rate-of-change splits apart without opening the YAML diff.
    if sat.subgroup is not None:
        description = (
            f"{sat.subgroup.title()} attributes for {sat.parent_hub} "
            f"({sat.change_velocity} change velocity)."
        )
    else:
        description = f"Descriptive attributes for {sat.parent_hub}."
    block: dict[str, Any] = {
        "name": sat.name,
        "description": description,
        "parent_hub": sat.parent_hub,
        "source_model": _staging_model_name(sat.source_table),
        "hash_key": sat.hash_key,
        "hashdiff": sat.hashdiff,
        "effective_from": sat.effective_from or _EFFECTIVE_FROM,
        "payload": list(sat.payload),
        "databricks_config": db.satellite_config(sat.hash_key, sat.hashdiff),
    }
    if sat.subgroup is not None:
        block["subgroup"] = sat.subgroup
    block["change_velocity"] = sat.change_velocity
    return block


def _link_block(link: LinkDecision) -> dict[str, Any]:
    driving_fk = link.fk_columns[0] if link.fk_columns else link.hash_key
    return {
        "name": link.name,
        "source_model": _staging_model_name(link.source_table),
        "hash_key": link.hash_key,
        "fk_columns": list(link.fk_columns),
        "databricks_config": db.link_config(link.hash_key, driving_fk),
    }


def _eff_sat_block(link: LinkDecision) -> dict[str, Any]:
    driving_fk = link.fk_columns[0] if link.fk_columns else link.hash_key
    secondary = list(link.fk_columns[1:]) if len(link.fk_columns) > 1 else []
    return {
        "name": _eff_sat_name(link.name),
        "parent_link": link.name,
        "source_model": _staging_model_name(link.source_table),
        "hash_key": link.hash_key,
        "driving_fk": driving_fk,
        "secondary_fk": secondary,
        "effective_from": _EFFECTIVE_FROM,
        "start_date": _START_DATE,
        "end_date": _END_DATE,
        "databricks_config": db.eff_sat_config(link.hash_key),
    }


def _staging_block(
    table: str,
    hubs: list[HubDecision],
    sats: list[SatelliteDecision],
    links: list[LinkDecision],
) -> dict[str, Any]:
    hashed = _hashed_columns(
        hubs=sorted(hubs, key=lambda h: h.name),
        sats=sorted(sats, key=lambda s: s.name),
    )
    # Add link hash keys (composite) to hashed_columns for tables that host links.
    for link in sorted(links, key=lambda ln: ln.name):
        if link.hash_key not in hashed:
            hashed[link.hash_key] = list(link.fk_columns)

    block: dict[str, Any] = {
        "name": _staging_model_name(table),
        "source_table": table,
        "databricks_config": db.staging_config(),
        "derived_columns": {
            "RECORD_SOURCE": "record_source",
            _LOAD_DATE: "load_dts",
            _EFFECTIVE_FROM: "load_dts",
            "CDC_FLAG": "cdc_flag",
            _START_DATE: "load_dts",
            _END_DATE: (
                "CASE WHEN cdc_flag = 'D' "
                "THEN CURRENT_TIMESTAMP "
                "ELSE CAST('9999-12-31' AS DATE) END"
            ),
            "IS_DELETED": "CASE WHEN cdc_flag = 'D' THEN TRUE ELSE FALSE END",
        },
    }
    if hashed:
        block["hashed_columns"] = hashed

    # ranked_columns: partition by BK of the first hub for this table.
    bk_col: str | None = None
    for hub in sorted(hubs, key=lambda h: h.name):
        if hub.business_keys:
            bk_col = hub.business_keys[0]
            break
    if bk_col:
        block["ranked_columns"] = {
            _DBTVAULT_RANK_COL: {"partition_by": bk_col, "order_by": _RANK_ORDER_BY}
        }
    return block


def _staging_blocks(plan: ModelingPlan) -> list[dict[str, Any]]:
    """One staging entry per source table, preserving first-seen order."""
    table_order: list[str] = []
    hubs_by_table: dict[str, list[HubDecision]] = {}
    sats_by_table: dict[str, list[SatelliteDecision]] = {}
    links_by_table: dict[str, list[LinkDecision]] = {}

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
        links_by_table.setdefault(link.source_table, []).append(link)

    return [
        _staging_block(
            table,
            hubs_by_table.get(table, []),
            sats_by_table.get(table, []),
            links_by_table.get(table, []),
        )
        for table in table_order
    ]


def _pit_block(
    pit: PitTable,
    hub_idx: dict[str, HubDecision],
) -> dict[str, Any]:
    hub = hub_idx.get(pit.parent_hub)
    hub_hk = hub.hash_key if hub else "HK_UNKNOWN"
    return {
        "name": pit.name,
        "description": f"PIT snapshot for the {pit.parent_hub} hub.",
        "hub": pit.parent_hub,
        "src_pk": hub_hk,
        "src_ldts": _LOAD_DATE,
        "satellites": [
            {"name": sat_name, "pk": hub_hk, "ldts": _LOAD_DATE}
            for sat_name in pit.satellites
        ],
        "databricks_config": db.pit_config(hub_hk),
    }


def _bridge_block(
    bridge: BridgeTable,
    hub_idx: dict[str, HubDecision],
    link_idx: dict[str, LinkDecision],
) -> dict[str, Any]:
    driving_hub_name = bridge.hub_keys[0] if bridge.hub_keys else ""
    driving_hub = hub_idx.get(driving_hub_name)
    hub_hk = driving_hub.hash_key if driving_hub else "HK_UNKNOWN"

    link = link_idx.get(bridge.parent_link)
    link_hk = link.hash_key if link else "HK_UNKNOWN"
    link_source = link.source_table if link else ""

    return {
        "name": bridge.name,
        "description": f"Bridge traversing {bridge.parent_link} between hubs.",
        "hub": driving_hub_name,
        "src_pk": hub_hk,
        "src_ldts": _LOAD_DATE,
        "bridge_walk": [
            {
                "link": bridge.parent_link,
                "eff_sat": _eff_sat_name(bridge.parent_link),
                "link_pk": link_hk,
                "link_fk": hub_hk,
            }
        ],
        "stage_tables": [_staging_model_name(link_source)] if link_source else [],
        "databricks_config": db.bridge_config(hub_hk, link_hk),
    }


def _dim_block(
    hub: HubDecision,
    sats: list[SatelliteDecision],
    pit_idx: dict[str, PitTable],
) -> dict[str, Any]:
    pit = pit_idx.get(hub.name)
    bk: Any = hub.business_keys[0] if len(hub.business_keys) == 1 else list(hub.business_keys)
    block: dict[str, Any] = {
        "name": _dim_name(hub),
        "description": f"Current state of {hub.source_table} (hub + PIT + satellites).",
        "hub": hub.name,
        "src_pk": hub.hash_key,
        "business_key": bk,
        "databricks_config": db.dim_config(),
        "satellites": [
            {"name": sat.name, "columns": list(sat.payload)} for sat in sats
        ],
    }
    if pit is not None:
        block["pit_table"] = pit.name
    return block


def _fact_block(
    bridge: BridgeTable,
    hub_idx: dict[str, HubDecision],
    link_idx: dict[str, LinkDecision],
) -> dict[str, Any]:
    link = link_idx.get(bridge.parent_link)
    grain = link.hash_key if link else "HK_UNKNOWN"
    dimensions = [
        _dim_name(hub_idx[hub_name])
        for hub_name in bridge.hub_keys
        if hub_name in hub_idx
    ]
    return {
        "name": _fact_name(bridge.name),
        "description": f"Fact view over {bridge.name}.",
        "bridge_table": bridge.name,
        "grain": grain,
        "src_ldts": _LOAD_DATE,
        "databricks_config": db.fact_config(),
        "dimensions": dimensions,
        "measures": [],
    }


def _bv_sat_block(
    bv_sat: BvSatellite,
    hub_idx: dict[str, HubDecision],
) -> dict[str, Any]:
    hub = hub_idx.get(bv_sat.parent_hub)
    hub_hk = hub.hash_key if hub else "HK_UNKNOWN"
    hashdiff = _bv_hashdiff(bv_sat.name)
    source_model = bv_sat.source_models[0] if bv_sat.source_models else ""

    # Prefer the rich payload (with per-column derivation_sql) when set.
    # Fall back to ``computed_columns`` for back-compat with callers that
    # pre-date :class:`BvSatPayloadItem`.
    effective = bv_sat.effective_payload
    payload_cols = [item.name for item in effective]
    derivation_rules = {
        item.name: item.derivation_sql
        for item in effective
        if item.derivation_sql is not None
    }

    block: dict[str, Any] = {
        "name": bv_sat.name,
        "description": f"Business vault satellite for {bv_sat.parent_hub}.",
        "parent_hub": bv_sat.parent_hub,
        "source_model": source_model,
        "hash_key": hub_hk,
        "hashdiff": hashdiff,
        "payload": payload_cols,
        "databricks_config": db.bv_sat_config(hub_hk, hashdiff),
    }
    if bv_sat.classification is not None:
        block["classification"] = bv_sat.classification.value
    if derivation_rules:
        # Emitted as a sibling map so PyYAML can serialise cleanly
        # (inline comments per list item are not possible with safe_dump).
        block["derivation_rules"] = derivation_rules
    if bv_sat.rationale:
        block["rationale"] = bv_sat.rationale
    return block


# ── Document assembler ────────────────────────────────────────────────────────


def _build_document(
    plan: ModelingPlan,
    system: SourceSystem,
    bv: BvProposal | None,
    *,
    load_frequency: str,
) -> dict[str, Any]:
    hub_idx = _hub_index(plan)
    sats_by_hub_map = _sats_by_hub(plan)
    link_idx = _link_index(plan)
    pit_idx = _pit_index(bv)

    doc: dict[str, Any] = {
        "system": _system_block(system, load_frequency=load_frequency),
        "packages": list(_DEFAULT_PACKAGES),
        "macros": list(_DEFAULT_MACROS),
        "hubs": [_hub_block(h) for h in plan.hubs],
        "satellites": [_sat_block(s) for s in plan.satellites],
        "links": [_link_block(ln) for ln in plan.links],
        "eff_sats": [_eff_sat_block(ln) for ln in plan.links],
        "staging": _staging_blocks(plan),
    }

    if bv is not None:
        if bv.pit_tables:
            doc["pit_tables"] = [_pit_block(p, hub_idx) for p in bv.pit_tables]
        if bv.bridge_tables:
            doc["bridge_tables"] = [
                _bridge_block(b, hub_idx, link_idx) for b in bv.bridge_tables
            ]

    # dim_tables: one per hub (requires at least one satellite for usefulness).
    dim_blocks = [
        _dim_block(hub, sats_by_hub_map.get(hub.name, []), pit_idx)
        for hub in plan.hubs
        if sats_by_hub_map.get(hub.name)
    ]
    if dim_blocks:
        doc["dim_tables"] = dim_blocks

    # fact_tables: one per bridge.
    if bv is not None and bv.bridge_tables:
        doc["fact_tables"] = [
            _fact_block(b, hub_idx, link_idx) for b in bv.bridge_tables
        ]

    if bv is not None and bv.bv_satellites:
        doc["bv_sats"] = [_bv_sat_block(s, hub_idx) for s in bv.bv_satellites]

    doc["databricks_optimization"] = db.global_optimization()
    return doc


def _dump(document: dict[str, Any]) -> str:
    """Serialise to a deterministic, human-readable YAML string."""
    buf = StringIO()
    yaml.safe_dump(
        document,
        buf,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    text = buf.getvalue()
    return text if text.endswith("\n") else text + "\n"


# ── Public API ────────────────────────────────────────────────────────────────


def render_v3(
    plan: ModelingPlan,
    system: SourceSystem,
    bv: BvProposal | None = None,
    *,
    load_frequency: str = "daily",
) -> str:
    """Return the full v3 metadata YAML string.

    Parameters
    ----------
    plan:
        Raw-vault modelling decisions from the SchemaAnalyzer.
    system:
        Source-system identity (catalog, schema, record_source …).
    bv:
        Optional business-vault proposal from the BV Architect.
        When ``None`` the BV sections (pit, bridge, dim, fact, bv_sats) are
        omitted so the document is still valid for raw-vault-only systems.
    load_frequency:
        Written into ``system.load_frequency``; defaults to ``"daily"``.
    """
    if plan.system_id != system.system_id:
        raise ValueError(
            f"Plan system_id '{plan.system_id}' does not match "
            f"SourceSystem.system_id '{system.system_id}'."
        )
    return _dump(_build_document(plan, system, bv, load_frequency=load_frequency))


def build_document(
    plan: ModelingPlan,
    system: SourceSystem,
    bv: BvProposal | None = None,
    *,
    load_frequency: str = "daily",
) -> dict[str, Any]:
    """Public dict-form of :func:`render_v3`.

    Returned dict is the same shape :func:`render_v3` serialises. Used
    by the orchestrator's DESCRIBE step to enrich descriptions before
    final YAML dump, and by tests that prefer structural assertions
    over string parsing.
    """
    if plan.system_id != system.system_id:
        raise ValueError(
            f"Plan system_id '{plan.system_id}' does not match "
            f"SourceSystem.system_id '{system.system_id}'."
        )
    return _build_document(plan, system, bv, load_frequency=load_frequency)


def dump_document(document: dict[str, Any]) -> str:
    """Serialise a document dict to canonical YAML.

    Exposed so the orchestrator can dump a (possibly enriched) document
    without reaching into private helpers.
    """
    return _dump(document)
