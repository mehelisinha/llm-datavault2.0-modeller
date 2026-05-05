"""Empirical column / table profiling from in-memory samples.

Inputs are deliberately limited to the lowest common denominator that all our
data sources can produce: a list of homogeneous mappings (``list[dict]``),
optionally constrained to a column subset. This keeps the profiler usable from:

* unit tests (synthetic dicts);
* the existing ``poc/`` runners (pandas ``DataFrame.to_dict('records')``);
* future Databricks jobs (Spark ``df.limit(N).collect()``).

What we deliberately do **not** do here:

* Connect to any database. That belongs in a thin adapter that yields rows
  into :func:`profile_table`.
* Sample at scale. The caller is expected to pass an already-sampled set of
  rows (typically 1k–10k); profiling is O(rows × columns) and not optimised
  for billions of rows.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from dbt_builder.src.ai.contracts.payloads import (
    ColumnProfile,
    SourceColumn,
    SourceTable,
)

_DEFAULT_SAMPLE_VALUES = 5
_KEY_CARDINALITY_THRESHOLD = 0.99  # ratio at/above which a column is "likely a key"


def _safe_str(value: Any) -> str:
    """Stringify a value, defaulting empty / None to the literal '<null>'."""
    if value is None:
        return "<null>"
    text = str(value)
    return text if text else "<empty>"


def profile_column(
    values: Iterable[Any],
    *,
    sample_value_count: int = _DEFAULT_SAMPLE_VALUES,
) -> ColumnProfile:
    """Build a :class:`ColumnProfile` from an iterable of raw column values.

    Parameters
    ----------
    values
        The column values, in any iterable form. Consumed exactly once.
    sample_value_count
        Maximum number of distinct sample values to retain. Sampling is
        order-preserving: the first ``N`` distinct non-null values seen are
        kept. Pass 0 to disable samples.

    Notes
    -----
    Distinct counts use a Python ``set`` and therefore require values to be
    hashable. Unhashable values (e.g. raw ``dict`` or ``list``) are stringified
    before insertion into the distinct set so the function never raises on
    nested data; this approximation is acceptable for profiling because the
    semantic type for such columns is ``JSON`` and exact distinct counts are
    rarely meaningful.
    """
    if sample_value_count < 0:
        raise ValueError("sample_value_count must be >= 0")

    row_count = 0
    null_count = 0
    distinct: set[Any] = set()
    samples: list[str] = []
    seen_samples: set[str] = set()

    for value in values:
        row_count += 1
        if value is None:
            null_count += 1
            continue
        try:
            distinct.add(value)
        except TypeError:
            distinct.add(str(value))

        if sample_value_count and len(samples) < sample_value_count:
            sample_text = _safe_str(value)
            if sample_text not in seen_samples:
                samples.append(sample_text)
                seen_samples.add(sample_text)

    distinct_count = len(distinct)
    non_null_count = row_count - null_count
    null_rate = (null_count / row_count) if row_count else 0.0
    cardinality_ratio = (distinct_count / non_null_count) if non_null_count else 0.0
    is_likely_key = (
        non_null_count > 0 and null_count == 0 and cardinality_ratio >= _KEY_CARDINALITY_THRESHOLD
    )

    return ColumnProfile(
        row_count=row_count,
        null_count=null_count,
        distinct_count=distinct_count,
        null_rate=round(null_rate, 6),
        cardinality_ratio=round(cardinality_ratio, 6),
        sample_values=tuple(samples),
        is_likely_key=is_likely_key,
    )


def profile_table(
    table: SourceTable,
    rows: Sequence[dict[str, Any]],
    *,
    sample_value_count: int = _DEFAULT_SAMPLE_VALUES,
    columns: Sequence[str] | None = None,
) -> SourceTable:
    """Return a copy of ``table`` with each column's :attr:`profile` populated.

    Parameters
    ----------
    table
        The schema-only :class:`SourceTable` (typically from
        :func:`discover_from_yaml`).
    rows
        Already-sampled rows. Each mapping must use the source column names as
        keys; missing keys are treated as ``None`` for that row.
    sample_value_count
        Forwarded to :func:`profile_column`.
    columns
        Optional subset of column names to profile. Columns not in this list
        keep their existing (typically absent) profile. Useful for incremental
        profiling on large tables.

    The returned :class:`SourceTable` is a brand-new immutable instance — the
    input ``table`` is not modified.
    """
    if columns is not None:
        target_names = {c.lower() for c in columns}
    else:
        target_names = {c.name.lower() for c in table.columns}

    new_columns: list[SourceColumn] = []
    for column in table.columns:
        if column.name.lower() not in target_names:
            new_columns.append(column)
            continue
        column_values = (row.get(column.name) for row in rows)
        profile = profile_column(column_values, sample_value_count=sample_value_count)
        # System columns must never be flagged as candidate business keys, no
        # matter how unique their values look in a sample.
        if column.is_system and profile.is_likely_key:
            profile = profile.model_copy(update={"is_likely_key": False})
        new_columns.append(column.model_copy(update={"profile": profile}))

    return table.model_copy(
        update={
            "columns": tuple(new_columns),
            "profiled_row_count": len(rows),
        }
    )
