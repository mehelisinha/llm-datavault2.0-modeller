"""Embedding generation, caching, and vector-store backends.

Phase 2 introduces semantic search over source-column descriptions so the
modelling agent can group related columns (likely satellite payloads) and
detect candidate hubs / links by name similarity.

Sub-modules:

* :mod:`vector_store`        — backend-agnostic Protocol + dataclasses.
* :mod:`faiss_store`         — local on-disk FAISS index (default; €0).
* :mod:`azure_search_store`  — Azure AI Search (any SKU) for production.
* :mod:`embedder`            — cached + retrying Azure OpenAI embedding client.

The active backend is selected by ``DWA_AI_VECTOR_BACKEND`` (``faiss`` |
``azure``) and constructed via :func:`get_vector_store`. Agents always depend
on the :class:`VectorStore` Protocol — never on a concrete implementation.
"""

from __future__ import annotations

from dbt_builder.src.ai.embeddings.embedder import (
    Embedder,
    EmbeddingCache,
    get_embedder,
)
from dbt_builder.src.ai.embeddings.vector_store import (
    SearchHit,
    VectorRecord,
    VectorStore,
    get_vector_store,
)

__all__ = [
    "Embedder",
    "EmbeddingCache",
    "SearchHit",
    "VectorRecord",
    "VectorStore",
    "get_embedder",
    "get_vector_store",
]
