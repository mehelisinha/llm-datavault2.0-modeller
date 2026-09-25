"""Tests for the YAML Generator agent.

Includes the byte-preservation snapshot test promised by Phase B4: rendering
the same plan + BV proposal twice MUST produce identical bytes, both for
each individual file and for the bundle as a whole. This is the property
that lets approvers diff plans line-by-line.

Also performs a round-trip with the ReferenceLoader: every emitted hub /
sat / link YAML must be re-parsable as a typed reference example. That
check guarantees the on-disk format stays in sync between the agent that
writes it and the loader that consumes it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dbt_builder.src.ai.agents import (
    BvArchitect,
    YamlBundle,
    YamlGenerator,
)
from dbt_builder.src.ai.agents.yaml_generator import (
    BRIDGE_DIR,
    BV_SAT_DIR,
    HUBS_DIR,
    LINKS_DIR,
    PIT_DIR,
    SATELLITES_DIR,
)
from dbt_builder.src.ai.contracts.bv import BvProposal, BvSatellite
from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.reference import ReferenceKind, ReferenceLoader


def _hub(name: str) -> HubDecision:
    return HubDecision(
        name=name,
        business_keys=("mrid",),
        source_table=name.removeprefix("hub_"),
        hash_key=f"HK_{name.removeprefix('hub_').upper()}",
        confidence=DecisionConfidence.HIGH,
        rationale="t",
    )


def _sat(name: str, parent_hub: str) -> SatelliteDecision:
    return SatelliteDecision(
        name=name,
        source_table=parent_hub.removeprefix("hub_"),
        parent_hub=parent_hub,
        hash_key=f"HK_{parent_hub.removeprefix('hub_').upper()}",
        hashdiff=f"HASHDIFF_{name.upper()}",
        payload=("col_a", "col_b"),
        confidence=DecisionConfidence.MEDIUM,
        rationale="t",
    )


def _link(name: str, fks: tuple[str, ...]) -> LinkDecision:
    return LinkDecision(
        name=name,
        source_table=name.removeprefix("link_"),
        hash_key=f"HK_{name.removeprefix('link_').upper()}",
        fk_columns=fks,
        confidence=DecisionConfidence.MEDIUM,
        rationale="t",
    )


def _full_plan() -> ModelingPlan:
    return ModelingPlan(
        system_id="iec_cim",
        hubs=(_hub("hub_terminal"), _hub("hub_node")),
        satellites=(
            _sat("sat_terminal_details", "hub_terminal"),
            _sat("sat_terminal_status", "hub_terminal"),
            _sat("sat_node_details", "hub_node"),
        ),
        links=(_link("link_terminal_node", ("HK_TERMINAL", "HK_NODE")),),
    )


# ── core determinism (B4 promise) ──────────────────────────────────────────


def test_render_is_byte_deterministic_across_runs() -> None:
    plan = _full_plan()
    bv = BvArchitect().propose(plan)
    gen = YamlGenerator()
    a = gen.render(plan=plan, bv=bv)
    b = gen.render(plan=plan, bv=bv)
    assert a == b
    # Stronger: byte-for-byte identical, not just dict-equal.
    assert tuple(f.body for f in a.files) == tuple(f.body for f in b.files)


def test_files_are_sorted_by_path() -> None:
    plan = _full_plan()
    bundle = YamlGenerator().render(plan=plan)
    paths = [f.path for f in bundle.files]
    assert paths == sorted(paths)


def test_bundle_paths_use_repo_layout() -> None:
    plan = _full_plan()
    bv = BvArchitect().propose(plan)
    bundle = YamlGenerator().render(plan=plan, bv=bv)
    paths = bundle.by_path().keys()
    assert (HUBS_DIR / "hub_terminal.yml").as_posix() in paths
    assert (SATELLITES_DIR / "sat_terminal_details.yml").as_posix() in paths
    assert (LINKS_DIR / "link_terminal_node.yml").as_posix() in paths
    assert (PIT_DIR / "pit_terminal.yml").as_posix() in paths
    assert (BRIDGE_DIR / "br_terminal_node.yml").as_posix() in paths


def test_bv_satellite_emitted_when_present() -> None:
    plan = ModelingPlan(system_id="iec_cim", hubs=(_hub("hub_terminal"),))
    bv = BvProposal(
        system_id="iec_cim",
        bv_satellites=(
            BvSatellite(
                name="bv_sat_terminal_score",
                parent_hub="hub_terminal",
                source_models=("hub_terminal",),
                computed_columns=("risk_score",),
            ),
        ),
    )
    bundle = YamlGenerator().render(plan=plan, bv=bv)
    assert (BV_SAT_DIR / "bv_sat_terminal_score.yml").as_posix() in bundle.by_path()


def test_render_rejects_mismatched_system_id() -> None:
    plan = _full_plan()
    bv = BvProposal(system_id="other_system")
    with pytest.raises(ValueError):
        YamlGenerator().render(plan=plan, bv=bv)


# ── format guarantees ──────────────────────────────────────────────────────


def test_each_file_ends_with_newline() -> None:
    bundle = YamlGenerator().render(plan=_full_plan())
    for f in bundle.files:
        assert f.body.endswith(b"\n")


def test_hub_yaml_matches_expected_meta() -> None:
    plan = _full_plan()
    bundle = YamlGenerator().render(plan=plan)
    hub_path = (HUBS_DIR / "hub_terminal.yml").as_posix()
    doc = yaml.safe_load(bundle.by_path()[hub_path])
    meta = doc["models"][0]["meta"]
    assert meta["dv_type"] == "hub"
    assert meta["src_pk"] == "HK_TERMINAL"
    assert meta["src_nk"] == "mrid"
    assert meta["source_models"] == ["stg_terminal"]


# ── round-trip with ReferenceLoader ────────────────────────────────────────


def test_emitted_yamls_are_loadable_by_reference_loader(tmp_path: Path) -> None:
    plan = _full_plan()
    bv = BvArchitect().propose(plan)
    bundle = YamlGenerator().render(plan=plan, bv=bv)
    YamlGenerator().write_to_disk(bundle, tmp_path)

    loader = ReferenceLoader(tmp_path / "models" / "raw_vault")
    names = {ex.name for ex in loader.all()}
    assert {"hub_terminal", "hub_node"} <= names
    assert {"sat_terminal_details", "sat_terminal_status", "sat_node_details"} <= names
    assert {"link_terminal_node"} <= names

    hubs = loader.by_kind(ReferenceKind.HUB)
    by_name = {h.name: h for h in hubs}
    assert by_name["hub_terminal"].src_pk == "HK_TERMINAL"
    assert by_name["hub_terminal"].source_models == ("stg_terminal",)


# ── disk write ─────────────────────────────────────────────────────────────


def test_write_to_disk_creates_expected_files(tmp_path: Path) -> None:
    bundle = YamlGenerator().render(plan=_full_plan())
    written = YamlGenerator().write_to_disk(bundle, tmp_path)
    assert len(written) == bundle.file_count
    for path in written:
        assert path.is_file()
        assert path.read_bytes().endswith(b"\n")


def test_write_to_disk_overwrites_existing_files(tmp_path: Path) -> None:
    bundle = YamlGenerator().render(plan=_full_plan())
    YamlGenerator().write_to_disk(bundle, tmp_path)
    # Mutate one file then re-write — generator must overwrite.
    target = tmp_path / bundle.files[0].path
    target.write_bytes(b"corrupted")
    YamlGenerator().write_to_disk(bundle, tmp_path)
    assert target.read_bytes() == bundle.files[0].body


# ── empty inputs ───────────────────────────────────────────────────────────


def test_empty_plan_produces_empty_bundle() -> None:
    plan = ModelingPlan(system_id="iec_cim")
    bundle = YamlGenerator().render(plan=plan)
    assert isinstance(bundle, YamlBundle)
    assert bundle.file_count == 0
