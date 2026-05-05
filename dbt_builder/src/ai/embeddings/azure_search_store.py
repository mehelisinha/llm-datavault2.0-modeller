"""Azure AI Search backend for the :class:`VectorStore` Protocol.

Lazy-creates a vector index named ``index_name`` configured with:

* ``id`` (key, string)
* ``content_vector`` (Collection(Edm.Single), HNSW profile, ``dimension`` dims)
* ``metadata_json`` (Edm.String, retrievable) — round-trips arbitrary metadata.

Cosine similarity is used to match the FAISS backend's semantics.

The implementation defers all ``azure.search.documents`` imports until the
class is instantiated so the rest of the AI package remains usable in
environments where only FAISS is installed.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from dbt_builder.src.ai.embeddings.vector_store import SearchHit, VectorRecord

_VECTOR_PROFILE = "dwa-hnsw-profile"
_HNSW_CONFIG = "dwa-hnsw-config"


class AzureSearchVectorStore:
    """Azure AI Search-backed vector store; works on F1 free through Standard."""

    def __init__(
        self,
        *,
        index_name: str,
        dimension: int,
        endpoint: str,
        admin_key: str,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")

        # Lazy imports: keep the FAISS-only path import-clean.
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient
        from azure.search.documents.indexes import SearchIndexClient

        self._index_name = index_name
        self._dimension = dimension
        self._credential = AzureKeyCredential(admin_key)
        self._endpoint = endpoint

        self._index_client = SearchIndexClient(endpoint, self._credential)
        self._ensure_index()
        self._search_client = SearchClient(endpoint, index_name, self._credential)

    @property
    def index_name(self) -> str:
        return self._index_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def upsert(self, records: Sequence[VectorRecord]) -> int:
        if not records:
            return 0
        docs: list[dict[str, Any]] = []
        for rec in records:
            if len(rec.vector) != self._dimension:
                raise ValueError(
                    f"Record {rec.id!r} has vector dim {len(rec.vector)}, "
                    f"expected {self._dimension}"
                )
            docs.append(
                {
                    "id": rec.id,
                    "content_vector": list(rec.vector),
                    "metadata_json": json.dumps(rec.metadata, ensure_ascii=False),
                }
            )
        results = self._search_client.merge_or_upload_documents(documents=docs)
        return sum(1 for r in results if r.succeeded)

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
        from azure.search.documents.models import VectorizedQuery

        vq = VectorizedQuery(
            vector=list(query_vector),
            k_nearest_neighbors=top_k,
            fields="content_vector",
        )
        results = self._search_client.search(
            search_text=None,
            vector_queries=[vq],
            select=["id", "metadata_json"],
            top=top_k,
        )
        hits: list[SearchHit] = []
        for doc in results:
            meta_raw = doc.get("metadata_json") or "{}"
            try:
                meta = json.loads(meta_raw)
            except json.JSONDecodeError:
                meta = {}
            hits.append(
                SearchHit(
                    id=doc["id"],
                    score=float(doc.get("@search.score", 0.0)),
                    metadata=meta,
                )
            )
        return hits

    def count(self) -> int:
        # Azure Search does not expose an O(1) count; ask for the document
        # count via the dedicated API on the index client.
        stats = self._index_client.get_index_statistics(self._index_name)
        return int(stats.get("document_count", 0))

    def delete_index(self) -> None:
        self._index_client.delete_index(self._index_name)

    # ------------------------------------------------------------------ Internals

    def _ensure_index(self) -> None:
        from azure.core.exceptions import ResourceNotFoundError
        from azure.search.documents.indexes.models import (
            HnswAlgorithmConfiguration,
            SearchableField,
            SearchField,
            SearchFieldDataType,
            SearchIndex,
            SimpleField,
            VectorSearch,
            VectorSearchProfile,
        )

        try:
            self._index_client.get_index(self._index_name)
            return
        except ResourceNotFoundError:
            pass

        index = SearchIndex(
            name=self._index_name,
            fields=[
                SimpleField(
                    name="id",
                    type=SearchFieldDataType.String,
                    key=True,
                    filterable=True,
                ),
                SearchField(
                    name="content_vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=self._dimension,
                    vector_search_profile_name=_VECTOR_PROFILE,
                ),
                SearchableField(
                    name="metadata_json",
                    type=SearchFieldDataType.String,
                    retrievable=True,
                    searchable=False,
                ),
            ],
            vector_search=VectorSearch(
                profiles=[
                    VectorSearchProfile(
                        name=_VECTOR_PROFILE,
                        algorithm_configuration_name=_HNSW_CONFIG,
                    )
                ],
                algorithms=[HnswAlgorithmConfiguration(name=_HNSW_CONFIG)],
            ),
        )
        self._index_client.create_index(index)
