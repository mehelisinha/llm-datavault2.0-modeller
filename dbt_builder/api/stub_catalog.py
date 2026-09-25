"""Auto-discover the stub catalog→schemas map from on-disk metadata YAMLs.

Phase B's discovery API has two modes:

* ``spark`` — calls Unity Catalog via Spark for the live list.
* ``stub``  — serves a fixed in-memory map so the UI works without Databricks.

Historically the stub map was a single hardcoded JSON literal on
:class:`ApiSettings`, which meant adding a new YAML under ``poc/metadata/``
had **no effect** on what the UI showed. That violated the project's
"YAML in ``poc/metadata`` is the single source of truth" rule.

This module provides two related capabilities:

1. :func:`discover_stub_catalog_map` — builds the ``{catalog: [schemas...]}``
   map the UI needs for its dropdowns, derived from YAMLs under ``poc/metadata/``.

2. :func:`make_stub_callables_for_catalog` — returns four callables
   ``(list_vault_entities, describe_vault, list_bronze_tables, describe_bronze)``
   for a given catalog, built from the matching discovery YAML. This keeps
   the stub snapshot endpoint catalog-aware without reaching into
   ``ai.pipeline.stub_fixtures`` (which the architecture test forbids).

The module is import-side-effect free: callers pass the directory and
default-vault-schema list explicitly.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Iterable

import yaml

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
"""Absolute path to the ``dwa/`` project root (``dwa/dbt_builder/api/`` -> 3 up)."""

DEFAULT_METADATA_DIR: Path = REPO_ROOT / "poc" / "metadata"
"""Where Phase-1 ``*_discovery.yaml`` and gold ``*_metadata.yaml`` files live."""

DEFAULT_VAULT_SCHEMAS: tuple[str, ...] = ("raw_vault",)
"""Schemas appended to every catalog so the UI can offer a vault-schema choice."""


def _iter_metadata_files(metadata_dir: Path) -> Iterable[Path]:
    """Yield every ``*.yaml`` / ``*.yml`` file directly under ``metadata_dir``.

    The directory is allowed to be missing — we yield nothing in that case
    rather than raising, because an empty repo (or a relocated metadata
    folder) should not break the API.
    """
    if not metadata_dir.is_dir():
        return
    for pattern in ("*.yaml", "*.yml"):
        yield from sorted(metadata_dir.glob(pattern))


def _read_yaml(path: Path) -> dict | None:
    """Return the top-level mapping from ``path`` or ``None`` if absent / malformed."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def _read_system_block(path: Path) -> dict[str, object] | None:
    """Return the ``system`` mapping from ``path`` or ``None`` if absent / malformed."""
    data = _read_yaml(path)
    if data is None:
        return None
    system = data.get("system")
    return system if isinstance(system, dict) else None


def discover_stub_catalog_map(
    metadata_dir: Path | str | None = None,
    *,
    default_vault_schemas: Iterable[str] = DEFAULT_VAULT_SCHEMAS,
) -> dict[str, list[str]]:
    """Build a ``{catalog: [schemas...]}`` map from YAMLs under ``metadata_dir``.

    Parameters
    ----------
    metadata_dir
        Directory to scan. ``None`` resolves to :data:`DEFAULT_METADATA_DIR`.
    default_vault_schemas
        Schemas appended to every catalog (deduplicated, order-preserving).

    Returns
    -------
    dict[str, list[str]]
        Sorted-stable, deduplicated catalog map. Schemas within a catalog
        preserve first-seen order (source schemas first, then defaults).
    """
    root = Path(metadata_dir) if metadata_dir is not None else DEFAULT_METADATA_DIR
    extras = tuple(default_vault_schemas)

    catalog_to_schemas: dict[str, list[str]] = {}
    for yaml_path in _iter_metadata_files(root):
        system = _read_system_block(yaml_path)
        if system is None:
            continue
        catalog = system.get("catalog")
        # Accept legacy 'schema' and forward-looking 'schema_name'.
        schema = system.get("schema") or system.get("schema_name")
        if not isinstance(catalog, str) or not catalog.strip():
            continue
        if not isinstance(schema, str) or not schema.strip():
            continue
        schemas = catalog_to_schemas.setdefault(catalog.strip(), [])
        if schema.strip() not in schemas:
            schemas.append(schema.strip())

    for catalog, schemas in catalog_to_schemas.items():
        for extra in extras:
            if extra and extra not in schemas:
                schemas.append(extra)

    return dict(sorted(catalog_to_schemas.items()))


# ---------------------------------------------------------------------------
# Per-catalog stub callables
# ---------------------------------------------------------------------------

# Type aliases matching the protocols expected by catalog_inspector / bronze_reader.
_ListEntities = Callable[[str, str], list[tuple[str, str]]]
_DescribeVault = Callable[[str, str, str], list[tuple[str, str, bool, str | None]]]
_ListTables = Callable[[str, str], list[str]]
_DescribeBronze = Callable[[str, str, str], list[tuple[str, str, bool, str | None, bool]]]


def _find_discovery_yaml(catalog: str, metadata_dir: Path) -> Path | None:
    """Return the first YAML under ``metadata_dir`` whose ``system.catalog`` == ``catalog``."""
    for yaml_path in _iter_metadata_files(metadata_dir):
        system = _read_system_block(yaml_path)
        if system and system.get("catalog") == catalog:
            return yaml_path
    return None


def _build_bronze_map(
    tables_raw: list,
) -> dict[str, list[tuple[str, str, bool, str | None, bool]]]:
    """Build a ``{table_name: [column_tuples...]}`` map from a raw ``tables`` list."""
    col_map: dict[str, list[tuple[str, str, bool, str | None, bool]]] = {}
    for entry in tables_raw:
        if not isinstance(entry, dict) or "name" not in entry:
            continue
        cols: list[tuple[str, str, bool, str | None, bool]] = []
        for col in entry.get("columns") or []:
            if not isinstance(col, dict) or "name" not in col:
                continue
            cols.append((
                str(col["name"]),
                str(col.get("raw_dtype", "string")),
                bool(col.get("nullable", True)),
                col.get("description"),
                False,  # is_partition — not tracked in discovery YAMLs
            ))
        col_map[str(entry["name"])] = cols
    return col_map


def make_stub_callables_for_catalog(
    catalog: str,
    metadata_dir: Path | str | None = None,
) -> tuple[_ListEntities, _DescribeVault, _ListTables, _DescribeBronze]:
    """Return four stub callables derived from the discovery YAML for ``catalog``.

    The callables match the signatures expected by
    :class:`dbt_builder.src.ai.service.DwaService`'s ``inspect_catalog`` and
    ``read_bronze`` methods.

    * **Vault** always returns empty — stub mode models a "fresh" source
      system where no DV objects exist yet. This ensures every bronze table
      is classified as ``new`` in the diff.
    * **Bronze** tables and columns are loaded from the ``*_discovery.yaml``
      (or ``*_metadata.yaml``) file whose ``system.catalog`` matches ``catalog``.
      Falls back to empty lists when no matching YAML is found so the API
      returns an empty but valid snapshot rather than raising.

    Parameters
    ----------
    catalog
        Unity Catalog name to match against ``system.catalog`` in the YAML files.
    metadata_dir
        Directory to scan. ``None`` resolves to :data:`DEFAULT_METADATA_DIR`.
    """
    root = Path(metadata_dir) if metadata_dir is not None else DEFAULT_METADATA_DIR
    yaml_path = _find_discovery_yaml(catalog, root)

    table_names: list[str] = []
    col_map: dict[str, list[tuple[str, str, bool, str | None, bool]]] = {}

    if yaml_path is not None:
        data = _read_yaml(yaml_path)
        if data is not None:
            tables_raw = data.get("tables") or []
            if isinstance(tables_raw, list):
                col_map = _build_bronze_map(tables_raw)
                table_names = list(col_map.keys())

    def list_vault_entities(_cat: str, _schema: str) -> list[tuple[str, str]]:
        return []

    def describe_vault(
        _cat: str, _schema: str, _table: str
    ) -> list[tuple[str, str, bool, str | None]]:
        return []

    def list_bronze_tables(_cat: str, _schema: str) -> list[str]:
        return list(table_names)

    def describe_bronze(
        _cat: str, _schema: str, table: str
    ) -> list[tuple[str, str, bool, str | None, bool]]:
        return list(col_map.get(table, []))

    return list_vault_entities, describe_vault, list_bronze_tables, describe_bronze


def list_tables_for_catalog(
    catalog: str,
    schema_name: str,
    metadata_dir: Path | str | None = None,
) -> tuple[str, ...]:
    """Return the table names for a given catalog and schema in stub mode.

    Reads the matching ``*_discovery.yaml`` file and returns the names of all
    tables it defines. Returns an empty tuple when no matching YAML is found
    so callers receive a valid (empty) response rather than raising.

    Parameters
    ----------
    catalog:
        Unity Catalog name to match against ``system.catalog``.
    schema_name:
        Schema name to match against ``system.schema`` / ``system.schema_name``.
    metadata_dir:
        Directory to scan. ``None`` resolves to :data:`DEFAULT_METADATA_DIR`.
    """
    root = Path(metadata_dir) if metadata_dir is not None else DEFAULT_METADATA_DIR
    for yaml_path in _iter_metadata_files(root):
        system = _read_system_block(yaml_path)
        if system is None:
            continue
        yaml_catalog = system.get("catalog")
        yaml_schema = system.get("schema") or system.get("schema_name")
        if yaml_catalog != catalog or yaml_schema != schema_name:
            continue
        data = _read_yaml(yaml_path)
        if data is None:
            return ()
        tables_raw = data.get("tables") or []
        return tuple(
            str(entry["name"])
            for entry in tables_raw
            if isinstance(entry, dict) and "name" in entry
        )
    return ()
