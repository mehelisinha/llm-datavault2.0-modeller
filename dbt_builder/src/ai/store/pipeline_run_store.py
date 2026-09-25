"""In-process store for :class:`PipelineRun` records.

This is deliberately ephemeral: a pipeline run is a *transient* coordination
artifact (the durable record of an approved model lives in the approval
store).  Keeping it in memory means:

* zero migration work when the contract evolves;
* the API can return rich, fully-typed objects without a serialisation hop;
* tests do not need a temp directory or sqlite teardown.

Thread-safety
-------------
Saves and reads take a single :class:`threading.Lock`. FastAPI worker
threads (and Uvicorn's worker pool) all share a single process for our
deployment topology, so a lock is sufficient. If we ever scale to multiple
processes the Protocol lets us swap in a Redis-backed implementation
without touching callers.

Capacity
--------
``max_retained`` (default 200) caps memory growth. Eviction is FIFO by
insertion order — the oldest run is discarded when the cap is reached.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Protocol

from dbt_builder.src.ai.contracts.pipeline_run import PipelineRun

_DEFAULT_MAX_RETAINED: int = 200


class PipelineRunStore(Protocol):
    """Minimum surface the API depends on."""

    def save(self, run: PipelineRun) -> None: ...

    def get(self, run_id: str) -> PipelineRun | None: ...

    def list_recent(self, *, limit: int = 50) -> tuple[PipelineRun, ...]: ...


class InMemoryPipelineRunStore:
    """Process-local replace-on-save store for :class:`PipelineRun`.

    Saving the same ``run_id`` twice replaces the prior record (this is how
    the orchestrator publishes incremental progress without spawning new
    rows per step).
    """

    def __init__(self, *, max_retained: int = _DEFAULT_MAX_RETAINED) -> None:
        if max_retained <= 0:
            raise ValueError("max_retained must be positive")
        self._max_retained = max_retained
        self._runs: OrderedDict[str, PipelineRun] = OrderedDict()
        self._lock = threading.Lock()

    def save(self, run: PipelineRun) -> None:
        with self._lock:
            if run.run_id in self._runs:
                # Move-to-end so the replaced entry is treated as newest.
                self._runs.move_to_end(run.run_id)
            self._runs[run.run_id] = run
            while len(self._runs) > self._max_retained:
                self._runs.popitem(last=False)

    def get(self, run_id: str) -> PipelineRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def list_recent(self, *, limit: int = 50) -> tuple[PipelineRun, ...]:
        if limit <= 0:
            return ()
        with self._lock:
            # OrderedDict iteration is insertion (== save) order; newest last.
            return tuple(reversed(list(self._runs.values())))[:limit]


# Convenience singleton — the API uses this by default; tests inject their own.
_default_store: InMemoryPipelineRunStore | None = None


def get_pipeline_run_store() -> InMemoryPipelineRunStore:
    """Return the process-wide default store, constructing it on first use."""
    global _default_store
    if _default_store is None:
        _default_store = InMemoryPipelineRunStore()
    return _default_store


def set_pipeline_run_store(store: InMemoryPipelineRunStore | None) -> None:
    """Replace the singleton (used by tests)."""
    global _default_store
    _default_store = store
