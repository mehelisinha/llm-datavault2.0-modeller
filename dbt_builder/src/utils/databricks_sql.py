"""Thin wrapper around ``databricks-sql-connector``.

A single helper used by every Delta-backed store (YAML versions, approval
audit trail). Centralising the connect / execute / fetch dance avoids
duplicating connection management in each store class and keeps the
``databricks.sql`` import truly lazy.
"""

from __future__ import annotations

import threading
from typing import Any, Sequence


class DatabricksSqlExecutor:
    """Lazy, lock-serialised wrapper for a Databricks SQL warehouse connection.

    Each store instance owns one executor. The connector itself is not
    thread-safe for parallel statements on the same connection, so a
    per-instance ``threading.Lock`` serialises writes/reads. For high
    concurrency, instantiate more stores (one per worker) — connections
    are cheap and the connector pools internally on the warehouse side.
    """

    def __init__(self, *, server_hostname: str, http_path: str, access_token: str) -> None:
        if not server_hostname or not http_path or not access_token:
            raise ValueError(
                "DatabricksSqlExecutor requires server_hostname, http_path and access_token."
            )
        self._server_hostname = server_hostname
        self._http_path = http_path
        self._access_token = access_token
        self._lock = threading.Lock()
        self._conn: Any | None = None

    def _ensure_conn(self) -> Any:
        if self._conn is None:
            from databricks import sql as _dbx_sql  # noqa: PLC0415 — lazy import

            self._conn = _dbx_sql.connect(
                server_hostname=self._server_hostname,
                http_path=self._http_path,
                access_token=self._access_token,
            )
        return self._conn

    def execute(self, statement: str, params: Sequence[Any] | None = None) -> None:
        with self._lock:
            conn = self._ensure_conn()
            cursor = conn.cursor()
            try:
                cursor.execute(statement, params or ())
            finally:
                cursor.close()

    def fetchall(
        self, statement: str, params: Sequence[Any] | None = None
    ) -> list[tuple[Any, ...]]:
        with self._lock:
            conn = self._ensure_conn()
            cursor = conn.cursor()
            try:
                cursor.execute(statement, params or ())
                return [tuple(row) for row in cursor.fetchall()]
            finally:
                cursor.close()

    def fetchone(
        self, statement: str, params: Sequence[Any] | None = None
    ) -> tuple[Any, ...] | None:
        with self._lock:
            conn = self._ensure_conn()
            cursor = conn.cursor()
            try:
                cursor.execute(statement, params or ())
                row = cursor.fetchone()
                return tuple(row) if row is not None else None
            finally:
                cursor.close()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None


__all__ = ["DatabricksSqlExecutor"]
