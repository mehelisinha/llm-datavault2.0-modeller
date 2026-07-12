"""Phase 2: learning-corpus exploder + DeltaExampleStore (stub executor)."""

from __future__ import annotations

import pytest

from dbt_builder.src.ai.contracts.decisions import (
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.store.corpus import make_example_store, plan_to_example_rows
from dbt_builder.src.utils.databricks_sql import DatabricksSqlExecutor
from dbt_builder.src.utils.yaml_store import (
    DeltaExampleStore,
    LocalExampleStore,
    RvExampleRow,
)


def _plan() -> ModelingPlan:
    return ModelingPlan(
        system_id="iec",
        hubs=(
            HubDecision(
                name="hub_terminal",
                source_table="terminals",
                business_keys=("mrid",),
                hash_key="HK_TERMINAL",
            ),
            HubDecision(
                name="hub_equipment",
                source_table="equipment",
                business_keys=("mrid",),
                hash_key="HK_EQUIPMENT",
            ),
        ),
        links=(
            LinkDecision(
                name="link_terminal_equipment",
                source_table="terminals",
                hash_key="HK_TERMINAL_EQUIPMENT",
                fk_columns=("HK_TERMINAL", "HK_EQUIPMENT"),
            ),
        ),
        satellites=(
            SatelliteDecision(
                name="sat_terminal_details",
                source_table="terminals",
                parent_hub="hub_terminal",
                hash_key="HK_TERMINAL",
                hashdiff="HD_TERMINAL",
                payload=("name", "phases"),
            ),
        ),
    )


# ── exploder ────────────────────────────────────────────────────────────────


def test_plan_explodes_to_one_row_per_raw_vault_object():
    rows = plan_to_example_rows(
        _plan(), catalog_id="iec", plan_id="p1", version=2, approved_by="u@example.com"
    )
    by_name = {r.object_name: r for r in rows}
    assert set(by_name) == {
        "hub_terminal",
        "hub_equipment",
        "link_terminal_equipment",
        "sat_terminal_details",
    }
    assert by_name["hub_terminal"].kind == "hub"
    assert by_name["link_terminal_equipment"].kind == "link"
    assert by_name["sat_terminal_details"].kind == "satellite"
    # provenance is carried through verbatim
    assert all(r.catalog == "iec" and r.version == 2 and r.plan_id == "p1" for r in rows)
    assert all(r.approved_by == "u@example.com" for r in rows)


def test_exploded_yaml_is_the_generator_output():
    rows = plan_to_example_rows(_plan(), catalog_id="iec", plan_id="p1", version=1, approved_by="u")
    hub = next(r for r in rows if r.object_name == "hub_terminal")
    # The stored text is the real dbt model YAML — the same envelope the on-disk
    # reference loader parses (dv_type in meta), so the two halves never drift.
    assert "dv_type: hub" in hub.yaml_text
    assert hub.source_path == "models/raw_vault/hubs/hub_terminal.yml"


# ── DeltaExampleStore (stubbed) ─────────────────────────────────────────────


class _StubExecutor(DatabricksSqlExecutor):
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.fetchall_rows: list[list[tuple]] = []

    def execute(self, statement, params=None):  # type: ignore[override]
        self.calls.append((statement, tuple(params or ())))

    def fetchall(self, statement, params=None):  # type: ignore[override]
        self.calls.append((statement, tuple(params or ())))
        return self.fetchall_rows.pop(0) if self.fetchall_rows else []


def _make_store() -> tuple[DeltaExampleStore, _StubExecutor]:
    exe = _StubExecutor()
    store = DeltaExampleStore(exe, catalog="dwa_meta", schema="dwa_meta", table="rv_examples")
    return store, exe


def test_constructor_ensures_schema_and_table():
    _, exe = _make_store()
    assert any("CREATE SCHEMA IF NOT EXISTS" in sql for sql, _ in exe.calls)
    assert any("CREATE TABLE IF NOT EXISTS" in sql for sql, _ in exe.calls)


def test_save_rows_inserts_each_with_sha256_and_returns_count():
    store, exe = _make_store()
    rows = [
        RvExampleRow(
            "iec",
            "p1",
            1,
            "hub_terminal",
            "hub",
            "models/raw_vault/hubs/hub_terminal.yml",
            "version: 2\n",
            "u",
        ),
        RvExampleRow(
            "iec",
            "p1",
            1,
            "sat_terminal_details",
            "satellite",
            "models/raw_vault/satellites/sat_terminal_details.yml",
            "version: 2\n",
            "u",
        ),
    ]
    n = store.save_rows(rows)
    assert n == 2
    inserts = [c for c in exe.calls if "INSERT INTO" in c[0]]
    assert len(inserts) == 2
    # params: catalog, plan_id, version, object_name, kind, source_path, text, sha256, actor
    _sql, params = inserts[0]
    assert params[3] == "hub_terminal" and params[4] == "hub" and len(params[7]) == 64


def test_load_latest_dedups_server_side_and_decodes():
    store, exe = _make_store()
    exe.fetchall_rows.append(
        [
            (
                "iec",
                "p1",
                3,
                "hub_terminal",
                "hub",
                "models/raw_vault/hubs/hub_terminal.yml",
                "version: 2\n",
                "lead@example.com",
            )
        ]
    )
    got = store.load_latest()
    assert len(got) == 1
    assert got[0].object_name == "hub_terminal" and got[0].version == 3
    # dedup is expressed in SQL (window function), not python
    assert any("ROW_NUMBER() OVER" in c[0] for c in exe.calls)


def test_invalid_identifier_rejected():
    exe = _StubExecutor()
    with pytest.raises(ValueError):
        DeltaExampleStore(exe, catalog="bad-name", schema="s", table="t")


# ── LocalExampleStore (filesystem corpus — Databricks-free) ──────────────────


def _row(obj="hub_terminal", kind="hub", version=1, text="version: 2\n"):
    return RvExampleRow(
        "iec", "p1", version, obj, kind, f"models/raw_vault/hubs/{obj}.yml", text, "u"
    )


def test_local_example_store_round_trip(tmp_path):
    store = LocalExampleStore(tmp_path / "corpus")
    assert store.save_rows([_row("hub_terminal"), _row("sat_x", "satellite")]) == 2
    loaded = store.load_latest()
    assert {r.object_name for r in loaded} == {"hub_terminal", "sat_x"}
    assert all(r.yaml_text == "version: 2\n" for r in loaded)  # payload preserved


def test_local_example_store_keeps_highest_version(tmp_path):
    store = LocalExampleStore(tmp_path / "corpus")
    store.save_rows([_row(version=2, text="v2")])
    store.save_rows([_row(version=1, text="v1")])  # lower version must NOT overwrite
    (only,) = store.load_latest()
    assert only.version == 2 and only.yaml_text == "v2"
    store.save_rows([_row(version=3, text="v3")])  # higher version overwrites
    (only,) = store.load_latest()
    assert only.version == 3 and only.yaml_text == "v3"


def test_local_example_store_empty(tmp_path):
    assert LocalExampleStore(tmp_path / "missing").load_latest() == ()


def test_make_example_store_local_backend_returns_local():
    from types import SimpleNamespace

    store = make_example_store(SimpleNamespace(metadata_store_backend="local"))
    assert isinstance(store, LocalExampleStore)
