"""Shared helpers for catalog + bronze snapshot construction."""

from __future__ import annotations

from datetime import datetime, timezone

from dbt_builder.src.ai.contracts.catalog import CatalogSnapshot


def greenfield_catalog_snapshot(catalog: str, bronze_schema: str) -> CatalogSnapshot:
    """Empty :class:`CatalogSnapshot` when no existing vault schema is provided.

    The diff analyzer matches bronze tables against ``catalog.entities``. With an
    empty entity tuple every bronze table reports as category NEW, which is
    the correct semantics for a first-time vault build where no ``hub_`` /
    ``lnk_`` / ``sat_`` objects exist yet.

    ``schema_name`` is required (``min_length=1``) by the contract, so we carry
    ``bronze_schema`` as a placeholder — it is never read by the diff because
    ``entities=()`` short-circuits every lookup.
    """
    return CatalogSnapshot(
        catalog=catalog,
        schema_name=bronze_schema,
        captured_at=datetime.now(timezone.utc),
        entities=(),
        metadata_yaml_path=None,
    )
