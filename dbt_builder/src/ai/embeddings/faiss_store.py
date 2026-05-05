"""On-disk FAISS implementation of :class:`VectorStore`.

Persistence layout (under ``cache_dir``):

* ``<index_name>.faiss`` — the FAISS index file (binary).
* ``<index_name>.meta.json`` — sidecar JSON containing ``{id, metadata}``
  rows aligned to the FAISS internal row order.

Why a sidecar JSON: FAISS itself stores only float vectors; ids and metadata
must live elsewhere. Keeping them in a JSON next to the index makes the cache
self-contained, human-inspectable, and trivially copyable across machines.

Concurrency
-----------
This store is **single-writer**. It holds the entire index in memory while
mutating, then atomically replaces both files on flush. Concurrent writers
will overwrite each other's last commit. The Phase 2 agent runs single-
process, so this is acceptable; if we later need multi-writer semantics we
should switch to the Azure backend.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from dbt_builder.src.ai.embeddings.vector_store import SearchHit, VectorRecord


def _normalize(matrix: np.ndarray) -> np.ndarray:
    """Row-normalise so inner-product == cosine similarity."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    # Replace zero norms with 1 to avoid division-by-zero; resulting row stays
    # all-zero so it can never be a top-k hit (max IP with anything is 0).
    norms[norms == 0] = 1.0
    return matrix / norms


class FaissVectorStore:
    """Single-file FAISS index with cosine similarity and JSON sidecar metadata."""

    def __init__(
        self,
        *,
        index_name: str,
        dimension: int,
        cache_dir: str | os.PathLike[str],
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._index_name = index_name
        self._dimension = dimension
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._cache_dir / f"{index_name}.faiss"
        self._meta_path = self._cache_dir / f"{index_name}.meta.json"

        self._index, self._rows = self._load_or_init()

    # ------------------------------------------------------------------ Protocol

    @property
    def index_name(self) -> str:
        return self._index_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def upsert(self, records: Sequence[VectorRecord]) -> int:
        if not records:
            return 0
        vectors_by_id: dict[str, VectorRecord] = {}
        for rec in records:
            if len(rec.vector) != self._dimension:
                raise ValueError(
                    f"Record {rec.id!r} has vector dim {len(rec.vector)}, "
                    f"expected {self._dimension}"
                )
            vectors_by_id[rec.id] = rec

        existing_ids = {row["id"] for row in self._rows}
        new_records = [r for r in vectors_by_id.values() if r.id not in existing_ids]
        replacements = [r for r in vectors_by_id.values() if r.id in existing_ids]

        if replacements:
            # FAISS IndexFlat does not support in-place updates; rebuild the
            # index whenever any id is replaced. For thesis-scale workloads
            # (<= a few thousand vectors) this is fast enough that the
            # simpler implementation is preferred over an IDMap workaround.
            self._rebuild_with_replacements(replacements)

        if new_records:
            matrix = _normalize(np.array([list(r.vector) for r in new_records], dtype=np.float32))
            self._index.add(matrix)
            for r in new_records:
                self._rows.append({"id": r.id, "metadata": dict(r.metadata)})

        self._flush()
        return len(records)

    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int = 5,
    ) -> list[SearchHit]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if len(query_vector) != self._dimension:
            raise ValueError(f"Query has dim {len(query_vector)}, expected {self._dimension}")
        if not self._rows:
            return []
        q = _normalize(np.array([list(query_vector)], dtype=np.float32))
        scores, indices = self._index.search(q, min(top_k, len(self._rows)))
        hits: list[SearchHit] = []
        for score, idx in zip(scores[0], indices[0], strict=False):
            if idx < 0 or idx >= len(self._rows):
                continue
            row = self._rows[int(idx)]
            hits.append(SearchHit(id=row["id"], score=float(score), metadata=dict(row["metadata"])))
        return hits

    def count(self) -> int:
        return len(self._rows)

    def delete_index(self) -> None:
        self._index = faiss.IndexFlatIP(self._dimension)
        self._rows = []
        for path in (self._index_path, self._meta_path):
            if path.exists():
                path.unlink()

    # ------------------------------------------------------------------ Internals

    def _load_or_init(self) -> tuple[Any, list[dict[str, Any]]]:
        if self._index_path.exists() and self._meta_path.exists():
            index = faiss.read_index(str(self._index_path))
            if index.d != self._dimension:
                raise ValueError(
                    f"Existing FAISS index '{self._index_name}' has dim {index.d}, "
                    f"requested {self._dimension}. Delete the cache file or pick a "
                    f"different index_name."
                )
            with self._meta_path.open("r", encoding="utf-8") as fh:
                rows = json.load(fh)
            return index, rows
        return faiss.IndexFlatIP(self._dimension), []

    def _rebuild_with_replacements(self, replacements: Sequence[VectorRecord]) -> None:
        replacement_map = {r.id: r for r in replacements}
        old_index = self._index
        old_rows = list(self._rows)

        self._index = faiss.IndexFlatIP(self._dimension)
        new_rows: list[dict[str, Any]] = []
        rebuilt_vectors: list[np.ndarray] = []

        for row_idx, row in enumerate(old_rows):
            if row["id"] in replacement_map:
                rec = replacement_map[row["id"]]
                # Replacement vectors arrive raw; normalise alongside the
                # reconstructed (already-normalised) ones below.
                rebuilt_vectors.append(
                    _normalize(np.array([list(rec.vector)], dtype=np.float32))[0]
                )
                new_rows.append({"id": rec.id, "metadata": dict(rec.metadata)})
            else:
                # IndexFlatIP retains raw (already-normalised) vectors and
                # supports reconstruct(i); reuse them so callers don't need
                # to re-supply unchanged records.
                rebuilt_vectors.append(old_index.reconstruct(row_idx))
                new_rows.append(row)

        if rebuilt_vectors:
            self._index.add(np.vstack(rebuilt_vectors).astype(np.float32))
        self._rows = new_rows

    def _flush(self) -> None:
        # Atomic write: stage to temp files in the same directory, then replace.
        tmp_index = tempfile.NamedTemporaryFile(delete=False, suffix=".faiss", dir=self._cache_dir)
        tmp_index.close()
        faiss.write_index(self._index, tmp_index.name)
        os.replace(tmp_index.name, self._index_path)

        tmp_meta = tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            suffix=".json",
            dir=self._cache_dir,
            encoding="utf-8",
        )
        try:
            json.dump(self._rows, tmp_meta, ensure_ascii=False, indent=2)
        finally:
            tmp_meta.close()
        os.replace(tmp_meta.name, self._meta_path)
