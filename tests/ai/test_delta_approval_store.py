"""Tests for DeltaApprovalStore against a stub DatabricksSqlExecutor."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from dbt_builder.src.ai.contracts.approval import ApprovalRecord, ApprovalStatus
from dbt_builder.src.ai.store import (
    ApprovalStoreError,
    DeltaApprovalStore,
)
from dbt_builder.src.utils.databricks_sql import DatabricksSqlExecutor


class _StubExecutor(DatabricksSqlExecutor):
    def __init__(self) -> None:
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


def _record(plan_id: str = "p1", version: int = 1) -> ApprovalRecord:
    return ApprovalRecord(
        plan_id=plan_id,
        version=version,
        status=ApprovalStatus.DRAFT,
        actor="user@example.com",
        timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        comment=None,
        plan_json='{"foo": "bar"}',
        validation_json=None,
        parent_plan_id=None,
        rendered_yaml="system:\n  catalog: iec\n",
        yaml_path=None,
    )


def _make_store() -> tuple[DeltaApprovalStore, _StubExecutor]:
    exe = _StubExecutor()
    store = DeltaApprovalStore(exe, catalog="dwa_meta", schema="default", table="approvals")
    return store, exe


def test_constructor_creates_table():
    _, exe = _make_store()
    assert any("CREATE TABLE IF NOT EXISTS" in sql for sql, _ in exe.calls)


def test_append_inserts_when_no_duplicate():
    store, exe = _make_store()
    # First fetchone (duplicate check) returns None → no duplicate.
    exe.fetchone_rows.append(None)

    store.append(_record())

    inserts = [c for c in exe.calls if "INSERT INTO" in c[0]]
    assert len(inserts) == 1
    _sql, params = inserts[0]
    assert params[0] == "p1"
    assert params[1] == 1
    assert params[2] == "draft"


def test_append_raises_on_duplicate():
    store, exe = _make_store()
    exe.fetchone_rows.append((1,))  # duplicate exists

    with pytest.raises(ApprovalStoreError):
        store.append(_record())


def test_latest_returns_none_when_empty():
    store, _ = _make_store()
    assert store.latest("missing") is None


def test_latest_decodes_row():
    store, exe = _make_store()
    exe.fetchone_rows.append(
        (
            "p1", 2, "approved", "lead@example.com",
            datetime(2026, 1, 5, tzinfo=timezone.utc),
            "ok", '{"plan":1}', None, None, "system: {}\n", "delta://...",
        )
    )
    rec = store.latest("p1")
    assert rec is not None
    assert rec.status is ApprovalStatus.APPROVED
    assert rec.version == 2
    assert rec.yaml_path == "delta://..."


def test_history_returns_ordered_tuples():
    store, exe = _make_store()
    exe.fetchall_rows.append(
        [
            (
                "p1", 1, "draft", "u", datetime(2026, 1, 1, tzinfo=timezone.utc),
                None, "{}", None, None, None, None,
            ),
            (
                "p1", 2, "approved", "u", datetime(2026, 1, 2, tzinfo=timezone.utc),
                None, "{}", None, None, None, None,
            ),
        ]
    )
    hist = store.history("p1")
    assert [r.version for r in hist] == [1, 2]
    assert [r.status.value for r in hist] == ["draft", "approved"]


def test_list_recent_uses_limit():
    store, exe = _make_store()
    exe.fetchall_rows.append([])
    store.list_recent(limit=7)
    fetched = [c for c in exe.calls if "LIMIT" in c[0]][-1]
    assert "LIMIT 7" in fetched[0]
