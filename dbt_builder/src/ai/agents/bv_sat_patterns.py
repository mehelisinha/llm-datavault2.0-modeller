"""Pattern-gated detector for business-vault satellite candidates.

We refuse to ask the LLM to *invent* business-vault satellites from
scratch. Two reasons:

1. Hallucination: the LLM happily proposes "tier", "score", "category"
   columns with derivation SQL that references columns that do not exist.
2. Reproducibility: a free-form proposal step makes pipeline output
   non-deterministic across runs of the same source data.

Instead, this module scans the raw-vault payloads for **named patterns**
that are known to map to a BV-sat rule (voltage tier, manufacturer
normalisation, status classification, asset age band, phase boolean).
Each detected pattern produces a :class:`BvSatCandidate` carrying:

* a deterministic name template (``bv_sat_<hub>_<pattern>``),
* a starter derivation SQL skeleton with placeholders bound to the
  actual source columns,
* a classification (NORMALISATION / CLASSIFICATION / ENRICHMENT).

The LLM proposer (:mod:`.bv_sat_proposer`) then asks the LLM to
**confirm and refine** these candidates — never to invent new ones
beyond what the patterns surfaced. If the catalogue has no matching
patterns, zero BV satellites are produced (controlled by
``DWA_AI_BV_SATS_ENABLED`` at the settings layer).

DRY: this module owns the entire BV-sat pattern catalogue. The proposer,
the renderer, and the tests all import :data:`PATTERNS` from here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from dbt_builder.src.ai.contracts.bv import BvSatClassification
from dbt_builder.src.ai.contracts.decisions import ModelingPlan


@dataclass(frozen=True)
class BvSatPattern:
    """One rule in the BV-sat pattern catalogue.

    Attributes
    ----------
    key
        Stable identifier used in the generated satellite name. Lowercase
        snake_case, e.g. ``voltage_tier``.
    column_regex
        Regex matched against payload column names (lowercased). The
        first matching column anchors the derivation.
    classification
        Rule family — drives the YAML ``classification`` field and helps
        reviewers triage proposals.
    derivation_template
        SQL skeleton with ``{col}`` placeholder. Replaced with the
        actual matching column name. Free-form — the YAML emitter writes
        this verbatim; the dbt model author may refine.
    output_columns_template
        Names of the columns the BV sat will emit, with ``{col}``
        placeholder. At least one column is required.
    rationale_template
        Short human explanation embedded in the BV satellite YAML so
        reviewers don't have to reverse-engineer the rule.
    """

    key: str
    column_regex: re.Pattern[str]
    classification: BvSatClassification
    derivation_template: str
    output_columns_template: tuple[str, ...]
    rationale_template: str


@dataclass(frozen=True)
class BvSatCandidate:
    """A pattern-derived BV-sat proposal, pre-LLM confirmation.

    The fields are deterministic functions of the source data, so two
    runs over the same catalogue produce identical candidates. The LLM
    proposer turns this into a final :class:`~dbt_builder.src.ai.contracts.bv.BvSatellite`.
    """

    pattern_key: str
    parent_hub: str
    source_table: str
    source_models: tuple[str, ...]
    name: str
    classification: BvSatClassification
    matched_column: str
    output_columns: tuple[str, ...]
    derivation_sql: str
    rationale: str


# ── Pattern catalogue ─────────────────────────────────────────────────────────
# Keep this list short and high-signal. Adding a low-precision pattern here
# silently produces noisy BV-sat proposals across every catalogue we touch.

PATTERNS: Final[tuple[BvSatPattern, ...]] = (
    BvSatPattern(
        key="voltage_tier",
        column_regex=re.compile(r"^(voltage|voltage_kv|nominal_voltage|voltage_level)$"),
        classification=BvSatClassification.CLASSIFICATION,
        derivation_template=(
            "case "
            "when {col} >= 110 then 'EHV' "
            "when {col} >= 36 then 'HV' "
            "when {col} >= 1 then 'MV' "
            "else 'LV' end"
        ),
        output_columns_template=("voltage_tier",),
        rationale_template=(
            "Standard utility voltage tiering (LV/MV/HV/EHV) derived from {col}; "
            "review thresholds against local regulation before promotion."
        ),
    ),
    BvSatPattern(
        key="manufacturer_normalised",
        column_regex=re.compile(r"^(manufacturer|vendor|maker)$"),
        classification=BvSatClassification.NORMALISATION,
        derivation_template="upper(trim({col}))",
        output_columns_template=("manufacturer_normalised",),
        rationale_template=(
            "Trim + uppercase {col} to provide a join-stable manufacturer key. "
            "Replace with a CDM-backed lookup once a reference table exists."
        ),
    ),
    BvSatPattern(
        key="operational_state",
        column_regex=re.compile(r"^(status|state|in_service|operational|connected)$"),
        classification=BvSatClassification.CLASSIFICATION,
        derivation_template=(
            "case "
            "when lower({col}) in ('in service','active','on','connected','true','1') then 'in_service' "
            "when lower({col}) in ('out of service','inactive','off','disconnected','false','0') then 'out_of_service' "
            "else 'unknown' end"
        ),
        output_columns_template=("operational_state",),
        rationale_template=(
            "Normalise free-text {col} to {{in_service, out_of_service, unknown}}; "
            "review value list against source enumerations before promotion."
        ),
    ),
    BvSatPattern(
        key="age_band",
        column_regex=re.compile(
            r"^(install_date|commission_date|commissioned|year_built|installation_date)$"
        ),
        classification=BvSatClassification.ENRICHMENT,
        derivation_template=(
            "case "
            "when datediff(current_date(), cast({col} as date)) / 365 < 10 then 'new' "
            "when datediff(current_date(), cast({col} as date)) / 365 < 25 then 'mid' "
            "when datediff(current_date(), cast({col} as date)) / 365 < 50 then 'aged' "
            "else 'legacy' end"
        ),
        output_columns_template=("age_band", "age_years"),
        rationale_template=(
            "Asset-age band derived from {col}; supports CAPEX planning and "
            "risk scoring. Adjust thresholds to match asset class."
        ),
    ),
    BvSatPattern(
        key="three_phase",
        column_regex=re.compile(r"^(phases?|phase_count|num_phases)$"),
        classification=BvSatClassification.CLASSIFICATION,
        derivation_template="cast({col} as int) = 3",
        output_columns_template=("is_three_phase",),
        rationale_template=(
            "Boolean flag for three-phase assets derived from {col}; simplifies "
            "downstream load-balance calculations."
        ),
    ),
)


# ── Public detector ──────────────────────────────────────────────────────────


def _hub_payload_columns(
    plan: ModelingPlan,
    hub_name: str,
) -> tuple[str, ...]:
    """Collect raw-vault satellite payload columns hanging off ``hub_name``."""
    cols: list[str] = []
    for sat in plan.satellites:
        if sat.parent_hub == hub_name:
            cols.extend(sat.payload)
    return tuple(cols)


def _staging_model_name(table_name: str) -> str:
    """Name of the staging model derived from a bare source table name.

    Mirrors the convention used by the YAML generator (``stg_<table>``).
    Kept as a small helper so a future convention change touches one
    line, not five.
    """
    return f"stg_{table_name}"


def detect_bv_candidates(
    plan: ModelingPlan,
) -> tuple[BvSatCandidate, ...]:
    """Scan the modelling plan for pattern-matching BV-sat opportunities.

    For each hub we look at its raw-vault satellite payloads. Every
    pattern in :data:`PATTERNS` is matched against the column names;
    each first match per (hub, pattern) yields one candidate. We
    intentionally cap at one candidate per (hub, pattern) because
    multiple voltage columns on the same hub almost always describe the
    same asset attribute under different aliases.

    Returns
    -------
    Tuple of :class:`BvSatCandidate`. Empty when no patterns match —
    the caller should treat that as "no BV sats this run".
    """
    seen_keys: set[tuple[str, str]] = set()
    out: list[BvSatCandidate] = []

    for hub in plan.hubs:
        # Build column → source_table map from the hub's satellites so we
        # can populate source_models accurately even when a hub is fed by
        # more than one source (rare but supported).
        col_to_table: dict[str, str] = {}
        for sat in plan.satellites:
            if sat.parent_hub != hub.name:
                continue
            for col in sat.payload:
                col_to_table.setdefault(col, sat.source_table)
        payload_cols = tuple(col_to_table.keys())
        if not payload_cols:
            continue

        for pattern in PATTERNS:
            dedup_key = (hub.name, pattern.key)
            if dedup_key in seen_keys:
                continue
            match_col = next(
                (c for c in payload_cols if pattern.column_regex.search(c.lower())),
                None,
            )
            if match_col is None:
                continue
            seen_keys.add(dedup_key)
            source_table = col_to_table[match_col]
            source_models = (_staging_model_name(source_table),)
            candidate = BvSatCandidate(
                pattern_key=pattern.key,
                parent_hub=hub.name,
                source_table=source_table,
                source_models=source_models,
                name=f"bv_sat_{hub.name.removeprefix('hub_')}_{pattern.key}",
                classification=pattern.classification,
                matched_column=match_col,
                output_columns=tuple(
                    name.format(col=match_col)
                    for name in pattern.output_columns_template
                ),
                derivation_sql=pattern.derivation_template.format(col=match_col),
                rationale=pattern.rationale_template.format(col=match_col),
            )
            out.append(candidate)
    return tuple(out)


__all__ = (
    "BvSatCandidate",
    "BvSatPattern",
    "PATTERNS",
    "detect_bv_candidates",
)
