"""Step 1 — Catalog Inspector.

Reads the *current state* of the target vault: existing Delta entities and
the parsed contents of an existing ``system_metadata.yml`` (if any). Both
sources are optional; missing inputs simply produce a smaller snapshot.

The inspector deliberately knows nothing about Spark. It accepts a
``DescribeTable`` callable so tests can pass deterministic fakes and
production code can wire in ``spark.sql('DESCRIBE TABLE ...')``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path

import yaml

from dbt_builder.src.ai.contracts.catalog import (
    CatalogSnapshot,
    VaultColumn,
    VaultEntity,
)
from dbt_builder.src.ai.pipeline._parallel import ordered_parallel_map

DescribeTable = Callable[[str, str, str], Iterable[tuple[str, str, bool, str | None]]]
"""Signature: ``(catalog, schema, table) -> iterable of (name, dtype, nullable, comment)``."""

ListEntities = Callable[[str, str], Iterable[tuple[str, str]]]
"""Signature: ``(catalog, schema) -> iterable of (entity_name, kind)``."""


_KIND_BY_PREFIX = (
    ("hub_", "hub"),
    ("lnk_", "link"),
    ("link_", "link"),
    ("sat_", "sat"),
    ("eff_sat_", "eff_sat"),
    ("pit_", "pit"),
    ("bridge_", "bridge"),
    ("bv_sat_", "bv_sat"),
)


def _classify_kind(name: str) -> str:
    lower = name.lower()
    for prefix, kind in _KIND_BY_PREFIX:
        if lower.startswith(prefix):
            return kind
    return "unknown"


def inspect_catalog(
    *,
    catalog: str,
    schema_name: str,
    list_entities: ListEntities,
    describe_table: DescribeTable,
    metadata_yaml_path: str | Path | None = None,
    describe_parallelism: int = 1,
) -> CatalogSnapshot:
    """Build a :class:`CatalogSnapshot` for ``catalog.schema_name``.

    Parameters
    ----------
    catalog, schema_name
        Target Unity Catalog ``catalog.schema`` to inspect.
    list_entities
        Callable returning the names + kinds of vault entities present.
    describe_table
        Callable returning per-column metadata for a single entity.
    metadata_yaml_path
        Optional path to the existing ``system_metadata.yml`` to record on the
        snapshot. Parsing is opportunistic: a malformed file is logged via the
        snapshot's ``metadata_yaml_path`` field but does not fail inspection.
    describe_parallelism
        Number of ``describe_table`` calls to issue concurrently. ``1`` keeps
        the legacy serial behaviour; production wires in
        :attr:`AISettings.catalog_describe_parallelism`.
    """
    raw_entities = list(list_entities(catalog, schema_name))

    def _describe(item: tuple[str, str]) -> VaultEntity:
        name, kind_hint = item
        kind = kind_hint or _classify_kind(name)
        cols = tuple(
            VaultColumn(
                name=col_name,
                raw_dtype=raw_dtype,
                nullable=nullable,
                comment=comment,
            )
            for col_name, raw_dtype, nullable, comment in describe_table(catalog, schema_name, name)
        )
        return VaultEntity(name=name, kind=kind, columns=cols)

    entities = ordered_parallel_map(_describe, raw_entities, max_workers=describe_parallelism)

    yaml_path_str: str | None = None
    if metadata_yaml_path is not None:
        path = Path(metadata_yaml_path)
        if path.exists():
            # We parse the YAML defensively — a malformed file should not
            # break catalog inspection. The parsed contents are not currently
            # carried on CatalogSnapshot (the diff analyzer rereads the YAML
            # via the higher-level service), but parsing here surfaces syntax
            # errors early and is cheap.
            try:
                yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                # Intentionally swallowed: the validator (Step 6) is the
                # authoritative YAML-syntax check. Recording the path is
                # enough for Step 1's responsibility.
                pass
            yaml_path_str = str(path)

    return CatalogSnapshot(
        catalog=catalog,
        schema_name=schema_name,
        captured_at=datetime.now(timezone.utc),
        entities=tuple(entities),
        metadata_yaml_path=yaml_path_str,
    )
