"""Deterministic rate-of-change heuristics for satellite splitting.

The modelling agent decides whether a hub's payload should be split into
``_details`` (quasi-static) vs ``_operational`` (frequently changing)
satellites. To keep that decision consistent across runs we feed the
modeller a deterministic **hint** instead of relying on the LLM to make
the call from scratch every time.

This module is the single source of truth for the split heuristic:

* :data:`OPERATIONAL_PATTERNS` — regex catalogue of column names that
  typically change at high velocity (status flags, connectivity, etc.).
* :data:`MEASUREMENT_PATTERNS` — regex catalogue for continuous numeric
  readings (sensor outputs, telemetry counters).
* :func:`classify_columns` — given a :class:`SourceTable`, partition its
  payload columns into ``{"details", "operational", "measurements"}``.
* :func:`build_hint` — produce a JSON-serialisable dict the modeller can
  embed in its user prompt verbatim.

DRY: every consumer (modeller prompt, future renderer, tests) imports
the patterns from here. No regex literals duplicated anywhere else.

Why deterministic rather than LLM-only?
---------------------------------------
The LLM is excellent at applying a rule once given. It is much less
consistent at *choosing* the rule from scratch under prompt pressure.
Pre-computing candidate buckets and asking the LLM to confirm/refine
gives us run-to-run stability without losing the LLM's judgement when
the heuristic guesses wrong.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from dbt_builder.src.ai.contracts.payloads import (
    InferredType,
    SourceColumn,
    SourceTable,
)

# ── Pattern catalogue ─────────────────────────────────────────────────────────
# Each entry is a compiled regex matched against the lowercased column name.
# Keep these intentionally conservative — false positives push columns into
# the wrong bucket, which is recoverable, but a fragmented satellite layout
# is harder to undo than a missing split.

OPERATIONAL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"^status$",
        r"_status$",
        r"^state$",
        r"_state$",
        r"^connected$",
        r"^is_[a-z0-9_]+$",        # is_active, is_enabled, is_open, ...
        r"^has_[a-z0-9_]+$",       # has_alarm, has_warning, ...
        r"_flag$",
        r"^flag$",
        r"^active$",
        r"^enabled$",
        r"^in_service$",
        r"^operational$",
        r"^current_[a-z0-9_]+$",   # current_state, current_phase, ...
        r"^last_[a-z0-9_]+_at$",   # last_seen_at, last_heartbeat_at, ...
        r"^heartbeat$",
        r"_state_at$",
    )
)

MEASUREMENT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"_reading$",
        r"_value$",
        r"_kw$",
        r"_kwh$",
        r"_kva$",
        r"_mva$",
        r"_mvar$",
        r"_amps?$",
        r"_volts?$",
        r"_celsius$",
        r"_fahrenheit$",
        r"_pressure$",
        r"_temperature$",
        r"_count$",
        r"_total$",
        r"^load_[a-z0-9_]+$",
        r"^measure[d]?_[a-z0-9_]+$",
    )
)

# Columns we never include in *any* satellite payload — exposed here so
# the heuristic and the modeller prompt share the same exclusion list.
SYSTEM_COLUMN_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"^load_dts$",
        r"^load_date$",
        r"^record_source$",
        r"^cdc_flag$",
        r"^effective_from$",
        r"^start_date$",
        r"^end_date$",
        r"^dl_[a-z0-9_]+$",
        r"^__[a-z0-9_]+$",
    )
)

# Cardinality ratio above which a column is considered key-like and
# therefore not a real payload column (would otherwise pollute the
# operational bucket via the ``is_*`` regex on a candidate key).
_KEY_LIKE_CARDINALITY = 0.95

# Minimum operational signals required to recommend an actual split.
# Splitting on a single ``status`` column is rarely worth the extra
# satellite; require at least 2 to call it a meaningful bucket.
MIN_OPERATIONAL_FOR_SPLIT = 2


def _matches(patterns: Iterable[re.Pattern[str]], name: str) -> bool:
    lowered = name.lower()
    return any(p.search(lowered) for p in patterns)


def _is_system_column(col: SourceColumn) -> bool:
    return col.is_system or _matches(SYSTEM_COLUMN_PATTERNS, col.name)


def _is_key_like(col: SourceColumn) -> bool:
    if col.profile is None:
        return False
    return (
        col.profile.is_likely_key
        or col.profile.cardinality_ratio >= _KEY_LIKE_CARDINALITY
    )


def classify_columns(
    table: SourceTable,
    *,
    excluded_columns: Iterable[str] = (),
) -> dict[str, list[str]]:
    """Bucket ``table`` payload columns by rate-of-change category.

    Parameters
    ----------
    table
        Source table to classify.
    excluded_columns
        Column names to omit entirely (hub business keys, FK columns
        already promoted to links, etc.). Case-insensitive.

    Returns
    -------
    Dict with three keys: ``"details"``, ``"operational"``, ``"measurements"``.
    Every key is always present (possibly mapped to an empty list) so
    downstream code can index without ``KeyError`` guards.
    """
    excluded = {c.lower() for c in excluded_columns}
    buckets: dict[str, list[str]] = {
        "details": [],
        "operational": [],
        "measurements": [],
    }
    for col in table.columns:
        if col.name.lower() in excluded:
            continue
        if _is_system_column(col):
            continue
        if _is_key_like(col):
            # Likely-unique columns are either the business key (already
            # excluded above) or a candidate FK — neither belongs in a
            # descriptive satellite payload.
            continue
        if _matches(OPERATIONAL_PATTERNS, col.name):
            buckets["operational"].append(col.name)
        elif _matches(MEASUREMENT_PATTERNS, col.name) and col.inferred_type in (
            InferredType.INTEGER,
            InferredType.FLOAT,
        ):
            buckets["measurements"].append(col.name)
        else:
            buckets["details"].append(col.name)
    return buckets


def build_hint(
    tables: Iterable[SourceTable],
    *,
    excluded_per_table: dict[str, Iterable[str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Produce a JSON-serialisable split hint for the modeller prompt.

    The returned mapping is keyed by bare table name and contains:

    * ``recommend_split`` — ``True`` when the operational or measurement
      bucket has at least :data:`MIN_OPERATIONAL_FOR_SPLIT` columns
      *and* the table also has descriptive columns. Hint only — the
      LLM may override either way.
    * ``reason`` — short explanation suitable for embedding in the prompt.
    * ``satellites_to_emit`` — an ordered list of **1:1 satellite
      blueprints** the modeller should copy into its ``satellites``
      output. Each entry uses the exact :class:`SatelliteDecision`
      field names (``subgroup``, ``change_velocity``, ``payload``) so
      the LLM has a literal template and cannot invent extras.

      - When ``recommend_split`` is ``False``, exactly one blueprint
        is emitted with ``subgroup=None`` and all non-key non-system
        columns in ``payload``.
      - When ``recommend_split`` is ``True``, one blueprint per
        non-empty bucket (``details`` / ``operational`` /
        ``measurements``) — empty buckets are omitted entirely so the
        LLM is never tempted to emit an empty satellite.

    Tables with no operational or measurement signals appear with
    ``recommend_split=False`` and a single-satellite blueprint so the
    modeller sees they were inspected (not silently omitted).
    """
    excluded_per_table = excluded_per_table or {}
    out: dict[str, dict[str, Any]] = {}
    for table in tables:
        buckets = classify_columns(
            table,
            excluded_columns=excluded_per_table.get(table.name, ()),
        )
        op_count = len(buckets["operational"])
        meas_count = len(buckets["measurements"])
        details_count = len(buckets["details"])
        recommend_split = (
            (op_count >= MIN_OPERATIONAL_FOR_SPLIT or meas_count >= MIN_OPERATIONAL_FOR_SPLIT)
            and details_count >= 1
        )
        if recommend_split:
            satellites: list[dict[str, Any]] = []
            if details_count >= 1:
                satellites.append({
                    "subgroup": "details",
                    "change_velocity": "static",
                    "payload": buckets["details"],
                })
            if op_count >= 1:
                satellites.append({
                    "subgroup": "operational",
                    "change_velocity": "dynamic",
                    "payload": buckets["operational"],
                })
            if meas_count >= 1:
                satellites.append({
                    "subgroup": "measurements",
                    "change_velocity": "dynamic",
                    "payload": buckets["measurements"],
                })
            reason = (
                f"{details_count} details + {op_count} operational + "
                f"{meas_count} measurement columns — rate-of-change split "
                f"recommended ({len(satellites)} satellites)."
            )
        else:
            merged = buckets["details"] + buckets["operational"] + buckets["measurements"]
            if op_count or meas_count:
                velocity = "mixed"
            elif details_count:
                velocity = "static"
            else:
                velocity = "mixed"
            satellites = [{
                "subgroup": None,
                "change_velocity": velocity,
                "payload": merged,
            }]
            reason = (
                f"{op_count} operational / {meas_count} measurement / "
                f"{details_count} details columns — no split needed; "
                "emit a single sat_<hub>."
            )
        out[table.name] = {
            "recommend_split": recommend_split,
            "reason": reason,
            "satellites_to_emit": satellites,
        }
    return out
