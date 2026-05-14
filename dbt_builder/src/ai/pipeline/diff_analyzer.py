"""Step 3 — Diff Analyzer.

Joins :class:`CatalogSnapshot` and :class:`BronzeSnapshot` to produce a
:class:`ChangeSet` categorising every bronze table NEW / DRIFT / UNCHANGED
plus every catalog entity with no bronze source as ORPHANED.

The diff is purely structural (column names + dtypes). Naming convention
matters: a bronze table ``conducting_equipment`` matches a vault entity
``hub_conducting_equipment`` (or ``sat_conducting_equipment_*``) by stripping
the ``hub_`` / ``sat_`` / ``lnk_`` prefix. Anything ambiguous is left for
Step 4 (Schema Analyzer LLM agent) to resolve.

High-risk changes (business-key rename, dtype change on a key column) are
flagged with :class:`ChangeRisk.HIGH` so the service facade can halt the
pipeline before any LLM call.
"""

from __future__ import annotations

from datetime import datetime, timezone

from dbt_builder.src.ai.contracts.catalog import (
    BronzeSnapshot,
    BronzeTable,
    CatalogSnapshot,
    ChangeCategory,
    ChangeRisk,
    ChangeSet,
    ColumnDiff,
    TableChange,
    VaultEntity,
)

_VAULT_PREFIXES = ("hub_", "lnk_", "link_", "sat_", "eff_sat_", "bv_sat_")


def _strip_vault_prefix(entity_name: str) -> str:
    lower = entity_name.lower()
    for prefix in _VAULT_PREFIXES:
        if lower.startswith(prefix):
            return lower[len(prefix) :]
    return lower


def _index_entities_by_source(entities: tuple[VaultEntity, ...]) -> dict[str, list[VaultEntity]]:
    """Group existing vault entities by their inferred source-table stem."""
    out: dict[str, list[VaultEntity]] = {}
    for entity in entities:
        stem = _strip_vault_prefix(entity.name)
        out.setdefault(stem, []).append(entity)
    return out


def _column_diffs(
    bronze: BronzeTable, vault: VaultEntity
) -> tuple[tuple[ColumnDiff, ...], ChangeRisk]:
    """Compute per-column diffs and roll them up to a coarse risk level."""
    bronze_by_name = {c.name.lower(): c for c in bronze.columns}
    vault_by_name = {c.name.lower(): c for c in vault.columns}

    diffs: list[ColumnDiff] = []
    risk = ChangeRisk.LOW
    bk_lower = (bronze.business_key or "").lower() or None

    added = set(bronze_by_name) - set(vault_by_name)
    removed = set(vault_by_name) - set(bronze_by_name)
    common = set(bronze_by_name) & set(vault_by_name)

    for name in sorted(added):
        col = bronze_by_name[name]
        diffs.append(ColumnDiff(name=col.name, change="added", new_dtype=col.raw_dtype))
    for name in sorted(removed):
        col = vault_by_name[name]
        diffs.append(ColumnDiff(name=col.name, change="removed", old_dtype=col.raw_dtype))
        if bk_lower is not None and name == bk_lower:
            risk = ChangeRisk.HIGH  # business-key disappeared
    for name in sorted(common):
        b_dtype = bronze_by_name[name].raw_dtype
        v_dtype = vault_by_name[name].raw_dtype
        if b_dtype != v_dtype:
            diffs.append(
                ColumnDiff(
                    name=bronze_by_name[name].name,
                    change="type_changed",
                    old_dtype=v_dtype,
                    new_dtype=b_dtype,
                )
            )
            if bk_lower is not None and name == bk_lower:
                risk = ChangeRisk.HIGH  # business-key dtype mutated
            elif risk is ChangeRisk.LOW:
                risk = ChangeRisk.MEDIUM

    if diffs and risk is ChangeRisk.LOW:
        risk = ChangeRisk.MEDIUM
    return tuple(diffs), risk


def diff(catalog: CatalogSnapshot, bronze: BronzeSnapshot) -> ChangeSet:
    """Produce a :class:`ChangeSet` from the two snapshots."""
    if catalog.catalog != bronze.catalog or catalog.schema_name != bronze.schema_name:
        # Catalog and bronze can legitimately live in different schemas;
        # what matters is the *vault* schema. We carry the vault one through.
        pass

    by_stem = _index_entities_by_source(catalog.entities)
    seen_stems: set[str] = set()
    changes: list[TableChange] = []

    for table in bronze.tables:
        stem = table.name.lower()
        seen_stems.add(stem)
        candidate_entities = by_stem.get(stem, [])

        if not candidate_entities:
            changes.append(
                TableChange(
                    table_name=table.name,
                    category=ChangeCategory.NEW,
                    risk=ChangeRisk.LOW,
                    notes=("No matching vault entity found for this bronze table.",),
                )
            )
            continue

        # Use the hub if one exists (most stable surface), otherwise the first.
        target = next(
            (e for e in candidate_entities if e.kind == "hub"),
            candidate_entities[0],
        )
        col_diffs, risk = _column_diffs(table, target)

        if not col_diffs:
            changes.append(
                TableChange(
                    table_name=table.name,
                    category=ChangeCategory.UNCHANGED,
                    risk=ChangeRisk.LOW,
                )
            )
        else:
            notes: list[str] = []
            bk = (table.business_key or "").lower()
            bk_removed = any(d.change == "removed" and bk == d.name.lower() for d in col_diffs)
            if bk_removed:
                notes.append("Business-key column removed — likely rename, halt pipeline.")
            changes.append(
                TableChange(
                    table_name=table.name,
                    category=ChangeCategory.DRIFT,
                    risk=risk,
                    column_diffs=col_diffs,
                    notes=tuple(notes),
                )
            )

    # Anything in the catalog with no matching bronze stem is ORPHANED.
    for stem, entities in by_stem.items():
        if stem in seen_stems:
            continue
        for entity in entities:
            changes.append(
                TableChange(
                    table_name=entity.name,
                    category=ChangeCategory.ORPHANED,
                    risk=ChangeRisk.MEDIUM,
                    notes=(f"Vault entity '{entity.name}' has no matching bronze source.",),
                )
            )

    # Stable ordering keeps the ChangeSet content-hash deterministic for the
    # idempotency guardrail test.
    changes.sort(key=lambda c: (c.category.value, c.table_name.lower()))

    return ChangeSet(
        catalog=catalog.catalog,
        schema_name=catalog.schema_name,
        computed_at=datetime.now(timezone.utc),
        changes=tuple(changes),
    )
