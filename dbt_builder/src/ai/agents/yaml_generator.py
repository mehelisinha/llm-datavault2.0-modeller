"""YAML Generator agent (Step 5 of the v2 metadata-generator pipeline).

Why a new generator
-------------------
The existing :mod:`dbt_builder.src.ai.rendering.yaml_emitter` produces a
single combined system-level YAML matching ``poc/metadata/iec_cim_metadata.yaml``.
That format was right for the Phase 2 prototype but the production layout
is per-object dbt model YAMLs under ``models/raw_vault/{hubs,satellites,links}/``
and ``models/business_vault/{pit,bridge,bv_sat}/`` — exactly what the
:class:`~dbt_builder.src.ai.reference.ReferenceLoader` already reads.

This generator:

* Emits **one YAML file per object**, matching the existing repo layout.
* Returns a typed :class:`YamlBundle` rather than writing to disk by default.
  Persistence is a separate, opt-in step so the generator stays pure and
  testable.
* Is **byte-deterministic**: identical inputs yield identical output bytes
  across runs — the property the snapshot test in
  ``tests/ai/test_yaml_generator_preservation.py`` enforces. This is what
  lets approvers diff plans line-by-line and trust that nothing moved
  underneath them.

Why no LLM call here
--------------------
By the time the YAML Generator runs, every decision has already been made:
the SchemaAnalyzer produced the raw-vault plan, the BV Architect produced
the BV proposal, the Validator approved both. Generating YAML is pure
serialisation — pulling an LLM into it would only add risk for zero gain.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.bv import (
    BridgeTable,
    BvProposal,
    BvSatellite,
    PitTable,
)
from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)

# ── Layout policy ───────────────────────────────────────────────────────────
# Centralised so the on-disk layout has one canonical definition. Tests
# import these constants instead of duplicating the string paths.

RAW_VAULT_ROOT = Path("models/raw_vault")
BUSINESS_VAULT_ROOT = Path("models/business_vault")

HUBS_DIR = RAW_VAULT_ROOT / "hubs"
SATELLITES_DIR = RAW_VAULT_ROOT / "satellites"
LINKS_DIR = RAW_VAULT_ROOT / "links"
PIT_DIR = BUSINESS_VAULT_ROOT / "pit"
BRIDGE_DIR = BUSINESS_VAULT_ROOT / "bridge"
BV_SAT_DIR = BUSINESS_VAULT_ROOT / "bv_sat"

# ── Naming convention ──────────────────────────────────────────────────────
# These mirror what the hand-written files already use (load_dts, hashdiff,
# RECORD_SOURCE, EFFECTIVE_FROM). Centralised so the YAML matches what the
# Validator expects, no divergence between agents.

_DEFAULT_LDTS_COL = "LOAD_DATE"
_DEFAULT_RECORD_SOURCE_COL = "RECORD_SOURCE"
_DEFAULT_EFFECTIVE_FROM_COL = "EFFECTIVE_FROM"


def _staging_model_name(source_table: str) -> str:
    return f"stg_{source_table}"


# ── Bundle types ───────────────────────────────────────────────────────────


class YamlFile(BaseModel):
    """One generated YAML file: a relative path + UTF-8 byte payload.

    Bytes (not str) so the byte-preservation snapshot test can assert true
    on-disk equality without worrying about platform line endings — the
    generator always writes ``\\n``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1, description="Repo-relative path with forward slashes.")
    body: bytes = Field(description="UTF-8 encoded YAML file contents.")


class YamlBundle(BaseModel):
    """Deterministic collection of generated YAML files.

    Files are sorted by path so two bundles built from the same inputs
    compare equal regardless of how the agent walked the plan.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    files: tuple[YamlFile, ...] = ()

    @property
    def file_count(self) -> int:
        return len(self.files)

    def by_path(self) -> dict[str, bytes]:
        return {f.path: f.body for f in self.files}


# ── Renderers (one per kind) ───────────────────────────────────────────────


def _dump(doc: dict[str, Any]) -> bytes:
    """yaml.safe_dump with deterministic settings.

    * ``sort_keys=False`` — preserve our ordering, which is the canonical one.
    * ``allow_unicode=True`` — pass through non-ASCII column comments.
    * ``default_flow_style=False`` — block style only; flow style varies
      across PyYAML versions.
    * Trailing newline guaranteed so ``cat file | wc -l`` matches.
    """
    buf = StringIO()
    yaml.safe_dump(
        doc,
        buf,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    text = buf.getvalue()
    if not text.endswith("\n"):
        text += "\n"
    return text.encode("utf-8")


def _hub_doc(hub: HubDecision) -> dict[str, Any]:
    business_key: Any
    if len(hub.business_keys) == 1:
        business_key = hub.business_keys[0]
    else:
        business_key = list(hub.business_keys)
    return {
        "version": 2,
        "models": [
            {
                "name": hub.name,
                "description": f"Data Vault hub for {hub.name}",
                "meta": {
                    "dv_type": "hub",
                    "source_models": [_staging_model_name(hub.source_table)],
                    "src_pk": hub.hash_key,
                    "src_nk": business_key,
                    "src_ldts": _DEFAULT_LDTS_COL,
                    "src_source": _DEFAULT_RECORD_SOURCE_COL,
                },
            }
        ],
    }


def _sat_doc(sat: SatelliteDecision) -> dict[str, Any]:
    return {
        "version": 2,
        "models": [
            {
                "name": sat.name,
                "description": f"Data Vault satellite for {sat.name}",
                "meta": {
                    "dv_type": "satellite",
                    "source_models": [_staging_model_name(sat.source_table)],
                    "src_pk": sat.hash_key,
                    "src_hashdiff": sat.hashdiff,
                    "src_payload": list(sat.payload),
                    "src_ldts": _DEFAULT_LDTS_COL,
                    "src_source": _DEFAULT_RECORD_SOURCE_COL,
                    "src_eff": sat.effective_from or _DEFAULT_EFFECTIVE_FROM_COL,
                },
            }
        ],
    }


def _link_doc(link: LinkDecision) -> dict[str, Any]:
    return {
        "version": 2,
        "models": [
            {
                "name": link.name,
                "description": f"Data Vault link {link.name}",
                "meta": {
                    "dv_type": "link",
                    "source_models": [_staging_model_name(link.source_table)],
                    "src_pk": link.hash_key,
                    "src_fk": list(link.fk_columns),
                    "src_ldts": _DEFAULT_LDTS_COL,
                    "src_source": _DEFAULT_RECORD_SOURCE_COL,
                },
            }
        ],
    }


def _pit_doc(pit: PitTable) -> dict[str, Any]:
    return {
        "version": 2,
        "models": [
            {
                "name": pit.name,
                "description": f"Point-in-time table for {pit.parent_hub}",
                "meta": {
                    "dv_type": "pit",
                    "parent_hub": pit.parent_hub,
                    "satellites": list(pit.satellites),
                    "granularity": pit.granularity,
                },
            }
        ],
    }


def _bridge_doc(bridge: BridgeTable) -> dict[str, Any]:
    return {
        "version": 2,
        "models": [
            {
                "name": bridge.name,
                "description": f"Bridge table over {bridge.parent_link}",
                "meta": {
                    "dv_type": "bridge",
                    "parent_link": bridge.parent_link,
                    "hub_keys": list(bridge.hub_keys),
                },
            }
        ],
    }


def _bv_sat_doc(sat: BvSatellite) -> dict[str, Any]:
    return {
        "version": 2,
        "models": [
            {
                "name": sat.name,
                "description": f"Business-vault satellite {sat.name}",
                "meta": {
                    "dv_type": "bv_sat",
                    "parent_hub": sat.parent_hub,
                    "source_models": list(sat.source_models),
                    "computed_columns": list(sat.computed_columns),
                },
            }
        ],
    }


# ── Generator ──────────────────────────────────────────────────────────────


class YamlGenerator:
    """Deterministically render a :class:`ModelingPlan` + :class:`BvProposal`.

    The generator is stateless — every call to :meth:`render` is a pure
    function of its inputs. There is no caching and no I/O. Use
    :meth:`write_to_disk` (or call a callback per file) to persist.
    """

    def render(
        self,
        *,
        plan: ModelingPlan,
        bv: BvProposal | None = None,
    ) -> YamlBundle:
        """Return a deterministic :class:`YamlBundle` for ``plan`` + ``bv``.

        When ``bv`` is supplied its ``system_id`` must match ``plan.system_id``;
        a mismatch is a programming error and is raised loudly rather than
        silently emitting a half-coherent bundle.
        """
        if bv is not None and bv.system_id != plan.system_id:
            raise ValueError(
                f"BV proposal system_id '{bv.system_id}' does not match "
                f"plan system_id '{plan.system_id}'."
            )

        files: list[YamlFile] = []

        for hub in plan.hubs:
            files.append(
                YamlFile(
                    path=(HUBS_DIR / f"{hub.name}.yml").as_posix(),
                    body=_dump(_hub_doc(hub)),
                )
            )
        for sat in plan.satellites:
            files.append(
                YamlFile(
                    path=(SATELLITES_DIR / f"{sat.name}.yml").as_posix(),
                    body=_dump(_sat_doc(sat)),
                )
            )
        for link in plan.links:
            files.append(
                YamlFile(
                    path=(LINKS_DIR / f"{link.name}.yml").as_posix(),
                    body=_dump(_link_doc(link)),
                )
            )

        if bv is not None:
            for pit in bv.pit_tables:
                files.append(
                    YamlFile(
                        path=(PIT_DIR / f"{pit.name}.yml").as_posix(),
                        body=_dump(_pit_doc(pit)),
                    )
                )
            for bridge in bv.bridge_tables:
                files.append(
                    YamlFile(
                        path=(BRIDGE_DIR / f"{bridge.name}.yml").as_posix(),
                        body=_dump(_bridge_doc(bridge)),
                    )
                )
            for bv_sat in bv.bv_satellites:
                files.append(
                    YamlFile(
                        path=(BV_SAT_DIR / f"{bv_sat.name}.yml").as_posix(),
                        body=_dump(_bv_sat_doc(bv_sat)),
                    )
                )

        # Sorting by path is the second half of the determinism guarantee.
        files.sort(key=lambda f: f.path)
        return YamlBundle(files=tuple(files))

    def write_to_disk(self, bundle: YamlBundle, root: Path | str) -> tuple[Path, ...]:
        """Persist ``bundle`` under ``root``. Returns the absolute paths written.

        Existing files are overwritten — the generator owns its output
        directories. Callers that want a non-destructive preview should
        compare the bundle in memory before calling this.
        """
        root_path = Path(root)
        written: list[Path] = []
        for file in bundle.files:
            target = root_path / file.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(file.body)
            written.append(target)
        return tuple(written)
