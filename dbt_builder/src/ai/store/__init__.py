"""Approval store: insert-only audit trail for plan reviews.

Two implementations are provided:

* :class:`SqliteApprovalStore` — local dev / CI; stdlib only.
* :class:`DeltaApprovalStore`  — production on Databricks (added in Phase C;
  this module exposes the Protocol so the service facade is implementation-
  agnostic from day one).

Both back the same :class:`ApprovalStore` Protocol. The store is **insert-
only**: every state transition is a new row keyed by ``(plan_id, version)``.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from dbt_builder.src.ai.contracts.approval import ApprovalRecord, ApprovalStatus


class ApprovalStoreError(RuntimeError):
    """Raised on any persistence failure (schema, conflict, IO)."""


class ApprovalStore(Protocol):
    """Minimum surface the service facade depends on."""

    def append(self, record: ApprovalRecord) -> None: ...

    def history(self, plan_id: str) -> tuple[ApprovalRecord, ...]: ...

    def latest(self, plan_id: str) -> ApprovalRecord | None: ...

    def list_recent(self, *, limit: int = 50) -> tuple[ApprovalRecord, ...]: ...


# ─── SQLite implementation ──────────────────────────────────────────────────


_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    plan_id           TEXT    NOT NULL,
    version           INTEGER NOT NULL,
    status            TEXT    NOT NULL,
    actor             TEXT    NOT NULL,
    timestamp_utc     TEXT    NOT NULL,
    comment           TEXT,
    plan_json         TEXT    NOT NULL,
    validation_json   TEXT,
    parent_plan_id    TEXT,
    rendered_yaml     TEXT,
    yaml_path         TEXT,
    PRIMARY KEY (plan_id, version)
);

CREATE INDEX IF NOT EXISTS idx_approvals_plan_id ON approvals(plan_id);
CREATE INDEX IF NOT EXISTS idx_approvals_timestamp ON approvals(timestamp_utc);
"""

# Migration: add columns to existing DBs that pre-date the rendered_yaml/yaml_path fields.
_MIGRATIONS = [
    "ALTER TABLE approvals ADD COLUMN rendered_yaml TEXT",
    "ALTER TABLE approvals ADD COLUMN yaml_path TEXT",
]


class SqliteApprovalStore:
    """Stdlib SQLite store. Safe for single-process dev usage.

    Concurrency: a per-instance ``threading.Lock`` serialises writes so the
    FastAPI dev server (uvicorn with --workers 1) won't corrupt the file.
    For multi-worker prod use the Delta-backed store.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            # Apply migrations idempotently for existing databases.
            for stmt in _MIGRATIONS:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass  # Column already exists.

    def _connect(self) -> sqlite3.Connection:
        # ``isolation_level=None`` lets us manage transactions explicitly per
        # write; combined with the per-instance lock this gives append-only
        # semantics without surprises on rollback.
        conn = sqlite3.connect(self._path, isolation_level=None, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def append(self, record: ApprovalRecord) -> None:
        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO approvals
                        (plan_id, version, status, actor, timestamp_utc,
                         comment, plan_json, validation_json, parent_plan_id,
                         rendered_yaml, yaml_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.plan_id,
                        record.version,
                        record.status.value,
                        record.actor,
                        record.timestamp.astimezone(timezone.utc).isoformat(),
                        record.comment,
                        record.plan_json,
                        record.validation_json,
                        record.parent_plan_id,
                        record.rendered_yaml,
                        record.yaml_path,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ApprovalStoreError(
                    f"Duplicate (plan_id={record.plan_id}, version={record.version})"
                ) from exc

    def history(self, plan_id: str) -> tuple[ApprovalRecord, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE plan_id = ? ORDER BY version ASC",
                (plan_id,),
            ).fetchall()
        return tuple(_row_to_record(r) for r in rows)

    def latest(self, plan_id: str) -> ApprovalRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approvals WHERE plan_id = ? ORDER BY version DESC LIMIT 1",
                (plan_id,),
            ).fetchone()
        return _row_to_record(row) if row else None

    def list_recent(self, *, limit: int = 50) -> tuple[ApprovalRecord, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM approvals ORDER BY timestamp_utc DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return tuple(_row_to_record(r) for r in rows)


def _row_to_record(row: sqlite3.Row) -> ApprovalRecord:
    keys = row.keys()
    return ApprovalRecord(
        plan_id=row["plan_id"],
        version=row["version"],
        status=ApprovalStatus(row["status"]),
        actor=row["actor"],
        timestamp=datetime.fromisoformat(row["timestamp_utc"]),
        comment=row["comment"],
        plan_json=row["plan_json"],
        validation_json=row["validation_json"],
        parent_plan_id=row["parent_plan_id"],
        rendered_yaml=row["rendered_yaml"] if "rendered_yaml" in keys else None,
        yaml_path=row["yaml_path"] if "yaml_path" in keys else None,
    )


# ─── helpers used by the service facade ──────────────────────────────────────


def make_record(
    *,
    plan_id: str,
    status: ApprovalStatus,
    actor: str,
    plan_json: str,
    validation_json: str | None,
    comment: str | None = None,
    parent_plan_id: str | None = None,
    previous_version: int | None = None,
    rendered_yaml: str | None = None,
    yaml_path: str | None = None,
) -> ApprovalRecord:
    """Build a record with auto-incremented version (caller passes prev)."""
    next_version = (previous_version or 0) + 1
    return ApprovalRecord(
        plan_id=plan_id,
        version=next_version,
        status=status,
        actor=actor,
        timestamp=datetime.now(timezone.utc),
        comment=comment,
        plan_json=plan_json,
        validation_json=validation_json,
        parent_plan_id=parent_plan_id,
        rendered_yaml=rendered_yaml,
        yaml_path=yaml_path,
    )


__all__ = [
    "ApprovalStore",
    "ApprovalStoreError",
    "SqliteApprovalStore",
    "make_record",
]
