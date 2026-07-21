"""Expand a table-grouped :class:`ChangeSet` into atomic, per-change units.

The diff engine emits one :class:`TableChange` per table (a DRIFT may carry
several column diffs). Impact classification and scoring (H2b) work most naturally
per *atomic* change — one added column, one removed column, one type change, one
new/removed table — so this module flattens a ChangeSet into that granularity,
assigning each atomic change its own risk (a key-column change/removal is HIGH).

Pure: no I/O, no LLM.
"""

from __future__ import annotations

from collections.abc import Iterable

from dbt_builder.src.ai.contracts.catalog import (
    ChangeCategory,
    ChangeRisk,
    TableChange,
)

_KEY_CHANGING = ("removed", "type_changed")


def _atomic_risk(change_verb: str, is_key: bool) -> ChangeRisk:
    """Per-column risk: HIGH for a key removal/retype, MEDIUM for other edits."""
    if is_key and change_verb in _KEY_CHANGING:
        return ChangeRisk.HIGH
    if change_verb in _KEY_CHANGING:
        return ChangeRisk.MEDIUM
    return ChangeRisk.LOW  # added column


def atomic_changes(
    change_set, *, key_columns: Iterable[str] = ()
) -> list[TableChange]:
    """Flatten ``change_set`` into one :class:`TableChange` per atomic change.

    NEW / ORPHANED / UNCHANGED tables stay as a single unit. A DRIFT table yields
    one unit per column diff, each carrying just that diff and a per-column risk.
    ``key_columns`` (lower-cased match) marks business-key columns so their
    removal/retype is flagged HIGH.
    """
    keys = {k.lower() for k in key_columns}
    out: list[TableChange] = []
    for change in change_set.changes:
        if change.category is not ChangeCategory.DRIFT or not change.column_diffs:
            out.append(change)
            continue
        for cd in change.column_diffs:
            out.append(
                TableChange(
                    table_name=change.table_name,
                    category=ChangeCategory.DRIFT,
                    risk=_atomic_risk(cd.change, cd.name.lower() in keys),
                    column_diffs=(cd,),
                    notes=change.notes,
                )
            )
    return out


__all__ = ["atomic_changes"]
