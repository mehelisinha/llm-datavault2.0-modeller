"""Tests for the FAISS-backed VectorStore.

These tests cover only the offline (FAISS) backend so they run on every
machine without any Azure credentials. The Azure backend is exercised
behind ``@pytest.mark.live`` in a later commit.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.ai

from dbt_builder.src.ai.embeddings import (  # noqa: E402
    SearchHit,
    VectorRecord,
    VectorStore,
    get_vector_store,
)
from dbt_builder.src.ai.embeddings.faiss_store import FaissVectorStore  # noqa: E402


def _vec(*values: float) -> tuple[float, ...]:
    return tuple(values)


def test_faiss_store_implements_protocol(tmp_path) -> None:
    store = FaissVectorStore(index_name="t", dimension=4, cache_dir=tmp_path)
    assert isinstance(store, VectorStore)
    assert store.index_name == "t"
    assert store.dimension == 4
    assert store.count() == 0


def test_upsert_and_search_returns_nearest_first(tmp_path) -> None:
    store = FaissVectorStore(index_name="t", dimension=3, cache_dir=tmp_path)
    store.upsert(
        [
            VectorRecord(id="a", vector=_vec(1.0, 0.0, 0.0), metadata={"tag": "x"}),
            VectorRecord(id="b", vector=_vec(0.0, 1.0, 0.0), metadata={"tag": "y"}),
            VectorRecord(id="c", vector=_vec(0.9, 0.1, 0.0), metadata={"tag": "x"}),
        ]
    )
    hits = store.search(_vec(1.0, 0.0, 0.0), top_k=2)
    assert [h.id for h in hits] == ["a", "c"]
    assert all(isinstance(h, SearchHit) for h in hits)
    assert hits[0].score > hits[1].score
    assert hits[0].metadata == {"tag": "x"}


def test_search_on_empty_index_returns_empty(tmp_path) -> None:
    store = FaissVectorStore(index_name="t", dimension=2, cache_dir=tmp_path)
    assert store.search(_vec(1.0, 0.0)) == []


def test_dimension_mismatch_raises(tmp_path) -> None:
    store = FaissVectorStore(index_name="t", dimension=3, cache_dir=tmp_path)
    with pytest.raises(ValueError):
        store.upsert([VectorRecord(id="a", vector=_vec(1.0, 0.0))])
    with pytest.raises(ValueError):
        store.search(_vec(1.0, 0.0))


def test_persistence_round_trip(tmp_path) -> None:
    store1 = FaissVectorStore(index_name="t", dimension=2, cache_dir=tmp_path)
    store1.upsert([VectorRecord(id="a", vector=_vec(1.0, 0.0), metadata={"k": 1})])
    # Re-open from disk in a new instance.
    store2 = FaissVectorStore(index_name="t", dimension=2, cache_dir=tmp_path)
    assert store2.count() == 1
    hits = store2.search(_vec(1.0, 0.0), top_k=1)
    assert hits[0].id == "a"
    assert hits[0].metadata == {"k": 1}


def test_upsert_replaces_existing_id(tmp_path) -> None:
    store = FaissVectorStore(index_name="t", dimension=2, cache_dir=tmp_path)
    store.upsert([VectorRecord(id="a", vector=_vec(1.0, 0.0), metadata={"v": 1})])
    store.upsert([VectorRecord(id="a", vector=_vec(0.0, 1.0), metadata={"v": 2})])
    assert store.count() == 1
    # Querying along the new direction should find 'a' on top.
    hits = store.search(_vec(0.0, 1.0), top_k=1)
    assert hits[0].id == "a"
    assert hits[0].metadata == {"v": 2}


def test_delete_index_removes_files(tmp_path) -> None:
    store = FaissVectorStore(index_name="t", dimension=2, cache_dir=tmp_path)
    store.upsert([VectorRecord(id="a", vector=_vec(1.0, 0.0))])
    assert (tmp_path / "t.faiss").exists()
    store.delete_index()
    assert not (tmp_path / "t.faiss").exists()
    assert not (tmp_path / "t.meta.json").exists()
    assert store.count() == 0


def test_reopening_with_wrong_dimension_raises(tmp_path) -> None:
    FaissVectorStore(index_name="t", dimension=4, cache_dir=tmp_path).upsert(
        [VectorRecord(id="a", vector=_vec(1.0, 0.0, 0.0, 0.0))]
    )
    with pytest.raises(ValueError):
        FaissVectorStore(index_name="t", dimension=8, cache_dir=tmp_path)


def test_factory_returns_faiss_when_configured(tmp_path, monkeypatch) -> None:
    # Use a fresh settings instance bypassing the lru_cache by monkeypatching.
    from dbt_builder.src.ai import settings as settings_mod

    fake_settings = settings_mod.AISettings(
        azure_subscription_id="sub",
        azure_resource_group="rg",
        azure_region="germanywestcentral",
        foundry_project_endpoint="https://x.example/api/projects/p",
        azure_openai_endpoint="https://x.openai.azure.com/",
        azure_openai_api_key="k",
        chat_deployment_gpt4o="gpt-4o",
        chat_deployment_gpt5="gpt-5",
        embedding_deployment="text-embedding-3-small",
        appinsights_connection_string="InstrumentationKey=00000000-0000-0000-0000-000000000000",
        vector_backend="faiss",
        vector_cache_dir=str(tmp_path),
    )
    store = get_vector_store("idx", dimension=4, settings=fake_settings)
    assert isinstance(store, FaissVectorStore)
    assert store.dimension == 4


def test_factory_rejects_azure_without_credentials(tmp_path) -> None:
    from dbt_builder.src.ai import settings as settings_mod

    fake_settings = settings_mod.AISettings(
        azure_subscription_id="sub",
        azure_resource_group="rg",
        azure_region="germanywestcentral",
        foundry_project_endpoint="https://x.example/api/projects/p",
        azure_openai_endpoint="https://x.openai.azure.com/",
        azure_openai_api_key="k",
        chat_deployment_gpt4o="gpt-4o",
        chat_deployment_gpt5="gpt-5",
        embedding_deployment="text-embedding-3-small",
        appinsights_connection_string="InstrumentationKey=00000000-0000-0000-0000-000000000000",
        vector_backend="azure",
        vector_cache_dir=str(tmp_path),
        search_endpoint=None,
        search_admin_key=None,
    )
    with pytest.raises(ValueError, match="DWA_AI_SEARCH_ENDPOINT"):
        get_vector_store("idx", dimension=4, settings=fake_settings)


def test_factory_rejects_unknown_backend(tmp_path) -> None:
    from dbt_builder.src.ai import settings as settings_mod

    fake_settings = settings_mod.AISettings(
        azure_subscription_id="sub",
        azure_resource_group="rg",
        azure_region="germanywestcentral",
        foundry_project_endpoint="https://x.example/api/projects/p",
        azure_openai_endpoint="https://x.openai.azure.com/",
        azure_openai_api_key="k",
        chat_deployment_gpt4o="gpt-4o",
        chat_deployment_gpt5="gpt-5",
        embedding_deployment="text-embedding-3-small",
        appinsights_connection_string="InstrumentationKey=00000000-0000-0000-0000-000000000000",
        vector_backend="pinecone",
        vector_cache_dir=str(tmp_path),
    )
    with pytest.raises(ValueError, match="Unknown vector_backend"):
        get_vector_store("idx", dimension=4, settings=fake_settings)
