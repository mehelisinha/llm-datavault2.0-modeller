"""Backend-agnostic vector-store interface and factory.

Goals
-----
* Keep modelling-agent code 100% backend-agnostic so Phase 2 dev can iterate
  with a fast local FAISS file while production runs on Azure AI Search.
* Make adding a new backend (Cosmos vector, pgvector, ...) a one-file change
  by depending only on the :class:`VectorStore` Protocol.

The Protocol exposes the smallest API needed by the Phase 2 agents:
``upsert``, ``search``, ``count``, ``delete_index``. Each backend persists a
single named index per :class:`VectorStore` instance; collections of indexes
are managed by constructing multiple stores.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from dbt_builder.src.ai.settings import AISettings


@dataclass(frozen=True)
class VectorRecord:
    """A single vector with its identifier and arbitrary metadata.

    ``id`` must be unique within an index; upserting an existing id replaces
    the previous record. ``vector`` must match the index's configured
    dimensionality. ``metadata`` is round-tripped verbatim through the
    backend (FAISS uses a sidecar JSON file; Azure stores it as document fields).
    """

    id: str
    vector: tuple[float, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHit:
    """A single hit returned by :meth:`VectorStore.search`."""

    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    """Minimum surface that every vector backend must implement."""

    @property
    def index_name(self) -> str:
        """Name of the index this store is bound to."""

    @property
    def dimension(self) -> int:
        """Vector dimensionality (e.g. 1536 for text-embedding-3-small)."""

    def upsert(self, records: Sequence[VectorRecord]) -> int:
        """Insert or replace ``records``; return the count actually written."""

    def search(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int = 5,
    ) -> list[SearchHit]:
        """Return up to ``top_k`` nearest neighbours by cosine similarity."""

    def count(self) -> int:
        """Return the number of records currently in the index."""

    def delete_index(self) -> None:
        """Remove the index (and any local artefacts)."""


def get_vector_store(
    index_name: str,
    *,
    dimension: int = 1536,
    settings: AISettings | None = None,
    backend: str | None = None,
) -> VectorStore:
    """Construct the configured :class:`VectorStore` for ``index_name``.

    Parameters
    ----------
    index_name
        Logical name of the index. The FAISS backend turns this into a
        filename under ``settings.vector_cache_dir``; the Azure backend
        creates / reuses a search index of the same name.
    dimension
        Vector dimension. Defaults to 1536 (text-embedding-3-small).
    settings
        Optional pre-loaded settings. Falls back to ``get_settings()``.
    backend
        Optional backend override (``'faiss'`` | ``'azure'``). When None,
        ``settings.vector_backend`` is used.

    Raises
    ------
    ValueError
        If ``backend`` is unknown or if the Azure backend is requested without
        ``search_endpoint`` / ``search_admin_key`` configured.
    """
    # Late imports keep the module importable without faiss / azure-search
    # installed; only the requested backend's dependency is touched.
    from dbt_builder.src.ai.settings import get_settings

    cfg = settings or get_settings()
    chosen = (backend or cfg.vector_backend).strip().lower()

    if chosen == "faiss":
        from dbt_builder.src.ai.embeddings.faiss_store import FaissVectorStore

        return FaissVectorStore(
            index_name=index_name,
            dimension=dimension,
            cache_dir=cfg.vector_cache_dir,
        )
    if chosen == "azure":
        if not cfg.search_endpoint or cfg.search_admin_key is None:
            raise ValueError(
                "vector_backend='azure' requires DWA_AI_SEARCH_ENDPOINT and "
                "DWA_AI_SEARCH_ADMIN_KEY to be set."
            )
        from dbt_builder.src.ai.embeddings.azure_search_store import (
            AzureSearchVectorStore,
        )

        return AzureSearchVectorStore(
            index_name=index_name,
            dimension=dimension,
            endpoint=cfg.search_endpoint,
            admin_key=cfg.search_admin_key.get_secret_value(),
        )
    raise ValueError(f"Unknown vector_backend '{chosen}'. Expected 'faiss' or 'azure'.")
