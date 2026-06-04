"""Internal helper: ordered, bounded-concurrency map.

Both :mod:`bronze_reader` and :mod:`catalog_inspector` issue one
``DESCRIBE TABLE`` round-trip per entity. On wide schemas this is an
N+1 latency cliff. The helper here parallelises those calls with a
thread pool while **preserving input order** so downstream snapshots
remain deterministic (and the idempotency guarantee asserted by
``tests/ai/test_diff_idempotency.py`` continues to hold).

Threads (not asyncio) because the wrapped callables — Databricks REST
clients, Spark SQL, the stub fixtures used in tests — are synchronous
and blocking on I/O; the GIL is released during those waits.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

_T = TypeVar("_T")
_R = TypeVar("_R")


def ordered_parallel_map(
    func: Callable[[_T], _R],
    items: Iterable[_T],
    *,
    max_workers: int,
) -> list[_R]:
    """Apply ``func`` to each item, returning results in input order.

    ``max_workers`` <= 1, or a single-item input, short-circuits to a
    plain serial loop so we don't pay thread-pool overhead on trivial
    inputs and so the call path stays identical to the pre-refactor
    behaviour for callers that explicitly opt out of concurrency.
    """
    materialised = list(items)
    if max_workers <= 1 or len(materialised) <= 1:
        return [func(item) for item in materialised]

    workers = min(max_workers, len(materialised))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(func, materialised))
