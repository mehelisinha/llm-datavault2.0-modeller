"""Tests for DeltaYamlStore against a stub DatabricksSqlExecutor.

The real executor is exercised in integration tests; here we stub it so
the suite can run without a Databricks warehouse.
"""

from __future__ import annotations

import hashlib

import pytest

from dbt_builder.src.utils.databricks_sql import DatabricksSqlExecutor
from dbt_builder.src.utils.yaml_store import DeltaYamlStore


class _StubExecutor(DatabricksSqlExecutor):
    """Stub that records executed SQL + params and serves canned fetch rows."""

    def __init__(self) -> None:
        # Bypass parent __init__ — we don't want it to validate creds.
        self.calls: list[tuple[str, tuple]] = []
        self.fetchone_rows: list[tuple | None] = []
        self.fetchall_rows: list[list[tuple]] = []

    def execute(self, statement, params=None):  # type: ignore[override]
        self.calls.append((statement, tuple(params or ())))

    def fetchone(self, statement, params=None):  # type: ignore[override]
        self.calls.append((statement, tuple(params or ())))
        return self.fetchone_rows.pop(0) if self.fetchone_rows else None

    def fetchall(self, statement, params=None):  # type: ignore[override]
        self.calls.append((statement, tuple(params or ())))
        return self.fetchall_rows.pop(0) if self.fetchall_rows else []


def _make_store() -> tuple[DeltaYamlStore, _StubExecutor]:
    exe = _StubExecutor()
    store = DeltaYamlStore(exe, catalog="dwa_meta", schema="default", table="yaml_versions")
    return store, exe


def test_constructor_creates_table_on_first_use():
    _, exe = _make_store()
    assert any("CREATE TABLE IF NOT EXISTS" in sql for sql, _ in exe.calls)
    assert any("PARTITIONED BY (catalog)" in sql for sql, _ in exe.calls)


def test_save_inserts_with_sha256_and_returns_url():
    store, exe = _make_store()
    yaml_text = "system:\n  catalog: iec\n"
    expected_digest = hashlib.sha256(yaml_text.encode("utf-8")).hexdigest()

    url = store.save(catalog_id="iec", plan_id="p1", version=3, rendered_yaml=yaml_text)

    insert_calls = [c for c in exe.calls if "INSERT INTO" in c[0]]
    assert len(insert_calls) == 1
    _sql, params = insert_calls[0]
    assert params == ("iec", "p1", 3, yaml_text, expected_digest)
    assert "delta://" in url
    assert "catalog=iec" in url
    assert "version=3" in url


def test_get_latest_returns_text_from_fetchone():
    store, exe = _make_store()
    exe.fetchone_rows.append(("system:\n  catalog: iec\n",))

    text = store.get_latest("iec")

    assert text.startswith("system:")
    assert any("ORDER BY created_at DESC" in c[0] for c in exe.calls)


def test_get_latest_raises_filenotfound_when_no_row():
    store, _ = _make_store()
    with pytest.raises(FileNotFoundError):
        store.get_latest("missing-catalog")


def test_invalid_identifier_rejected():
    exe = _StubExecutor()
    with pytest.raises(ValueError):
        DeltaYamlStore(exe, catalog="bad-name", schema="default", table="t")
    with pytest.raises(ValueError):
        DeltaYamlStore(exe, catalog="ok", schema="default", table="bad table")


def test_executor_type_enforced():
    with pytest.raises(TypeError):
        DeltaYamlStore(object(), catalog="dwa_meta", schema="default", table="t")
