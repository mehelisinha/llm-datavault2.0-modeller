"""Tests for the deterministic reference-YAML loader (RAG replacement)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dbt_builder.src.ai.reference import (
    ReferenceExample,
    ReferenceKind,
    ReferenceLoader,
)

_HUB_YML = """\
version: 2
models:
- name: hub_terminal
  description: Data Vault hub for hub_terminal
  meta:
    dv_type: hub
    source_models:
    - stg_terminals
    src_pk: HK_TERMINAL
    src_nk: mrid
    src_ldts: LOAD_DATE
    src_source: RECORD_SOURCE
"""

_SAT_YML = """\
version: 2
models:
- name: sat_terminal_details
  description: Data Vault satellite for sat_terminal_details
  meta:
    dv_type: satellite
    source_models:
    - stg_terminals
    src_pk: HK_TERMINAL
    src_hashdiff: HASHDIFF_TERMINAL_DETAILS
    src_payload:
    - name
    - sequence_number
    src_ldts: LOAD_DATE
    src_source: RECORD_SOURCE
    src_eff: EFFECTIVE_FROM
"""

_LINK_YML = """\
version: 2
models:
- name: link_terminal_node
  description: DV link terminal <-> connectivity_node
  meta:
    dv_type: link
    source_models:
    - stg_terminals
    src_pk: HK_TERMINAL_NODE
    src_fk:
    - HK_TERMINAL
    - HK_CONNECTIVITY_NODE
    src_ldts: LOAD_DATE
    src_source: RECORD_SOURCE
"""

_INVALID_YML = """\
this: is not a dbt models envelope
just: a random mapping
"""


@pytest.fixture()
def reference_root(tmp_path: Path) -> Path:
    """Build a minimal raw_vault tree on disk."""
    (tmp_path / "hubs").mkdir()
    (tmp_path / "satellites").mkdir()
    (tmp_path / "links").mkdir()
    (tmp_path / "hubs" / "hub_terminal.yml").write_text(_HUB_YML, encoding="utf-8")
    (tmp_path / "satellites" / "sat_terminal_details.yml").write_text(_SAT_YML, encoding="utf-8")
    (tmp_path / "links" / "link_terminal_node.yml").write_text(_LINK_YML, encoding="utf-8")
    # Garbage file should be skipped, not crash the loader.
    (tmp_path / "hubs" / "broken.yml").write_text(_INVALID_YML, encoding="utf-8")
    return tmp_path


def test_loader_parses_all_kinds(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    kinds = {ex.kind for ex in loader.all()}
    assert kinds == {ReferenceKind.HUB, ReferenceKind.SATELLITE, ReferenceKind.LINK}


def test_loader_skips_invalid_files(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    names = {ex.name for ex in loader.all()}
    assert "broken" not in names
    assert names == {"hub_terminal", "sat_terminal_details", "link_terminal_node"}


def test_loader_extracts_hub_fields(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    (hub,) = loader.by_kind(ReferenceKind.HUB)
    assert hub.src_pk == "HK_TERMINAL"
    assert hub.src_nk == "mrid"
    assert hub.source_models == ("stg_terminals",)


def test_loader_extracts_satellite_payload(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    (sat,) = loader.by_kind(ReferenceKind.SATELLITE)
    assert sat.src_hashdiff == "HASHDIFF_TERMINAL_DETAILS"
    assert sat.src_payload == ("name", "sequence_number")


def test_loader_extracts_link_fks(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    (link,) = loader.by_kind(ReferenceKind.LINK)
    assert link.src_fk == ("HK_TERMINAL", "HK_CONNECTIVITY_NODE")


def test_select_relevant_ranks_by_lexical_overlap(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    picks = loader.select_relevant("terminal", limit=2)
    assert len(picks) == 2
    assert all("terminal" in ex.name for ex in picks)


def test_select_relevant_is_deterministic(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    a = loader.select_relevant("terminal", limit=3)
    b = loader.select_relevant("terminal", limit=3)
    assert tuple(ex.name for ex in a) == tuple(ex.name for ex in b)


def test_select_relevant_filter_by_kind(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    picks = loader.select_relevant("terminal", kinds=[ReferenceKind.SATELLITE], limit=3)
    assert {ex.kind for ex in picks} == {ReferenceKind.SATELLITE}


def test_select_relevant_returns_empty_for_unknown_target(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    assert loader.select_relevant("totally_unrelated_xyz", limit=3) == ()


def test_to_prompt_block_includes_key_fields(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    block = loader.to_prompt_block(loader.by_kind(ReferenceKind.HUB))
    assert "hub_terminal" in block
    assert "HK_TERMINAL" in block
    assert "stg_terminals" in block


def test_to_prompt_block_handles_empty(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    assert "no reference examples" in loader.to_prompt_block([])


def test_loader_handles_missing_root(tmp_path: Path) -> None:
    loader = ReferenceLoader(tmp_path / "does_not_exist")
    assert loader.all() == ()


def test_examples_are_immutable(reference_root: Path) -> None:
    loader = ReferenceLoader(reference_root)
    ex = loader.all()[0]
    with pytest.raises(ValidationError):
        ex.name = "mutated"  # type: ignore[misc]
    assert isinstance(ex, ReferenceExample)
