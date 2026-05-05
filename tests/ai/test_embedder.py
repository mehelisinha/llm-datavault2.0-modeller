"""Tests for the cached, retrying Embedder.

These tests use a fake Azure OpenAI client so they run offline. The live
embedding endpoint is exercised behind ``@pytest.mark.live`` in commit #6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

pytestmark = pytest.mark.ai

from openai import APIConnectionError  # noqa: E402

from dbt_builder.src.ai.embeddings.embedder import (  # noqa: E402
    Embedder,
    EmbeddingCache,
    _hash_key,
)


@dataclass
class _FakeItem:
    embedding: list[float]


@dataclass
class _FakeResponse:
    data: list[_FakeItem]


class _FakeEmbeddings:
    def __init__(self, *, fail_times: int = 0) -> None:
        self.calls: list[list[str]] = []
        self._fail_times = fail_times

    def create(self, *, model: str, input: list[str]) -> _FakeResponse:  # noqa: A002
        self.calls.append(list(input))
        if self._fail_times > 0:
            self._fail_times -= 1
            raise APIConnectionError(request=None)  # type: ignore[arg-type]
        # Deterministic vector: [len(text), index_in_batch, 0.0, 0.0]
        return _FakeResponse(
            data=[
                _FakeItem(embedding=[float(len(t)), float(i), 0.0, 0.0])
                for i, t in enumerate(input)
            ]
        )


class _FakeClient:
    def __init__(self, embeddings: _FakeEmbeddings) -> None:
        self.embeddings = embeddings


def _make(client: Any, *, cache_dir, batch_size: int = 256) -> Embedder:
    return Embedder(
        client=client,
        model="text-embedding-3-small",
        cache=EmbeddingCache(cache_dir),
        batch_size=batch_size,
    )


def test_embed_returns_one_vector_per_input(tmp_path) -> None:
    fake = _FakeEmbeddings()
    e = _make(_FakeClient(fake), cache_dir=tmp_path)
    out = e.embed(["alpha", "bravo"])
    assert len(out) == 2
    assert all(isinstance(v, tuple) and len(v) == 4 for v in out)


def test_cache_hit_skips_api_on_second_call(tmp_path) -> None:
    fake = _FakeEmbeddings()
    e = _make(_FakeClient(fake), cache_dir=tmp_path)
    e.embed(["hello", "world"])
    assert len(fake.calls) == 1
    e.embed(["hello", "world"])
    # No new API call: both texts are cached on disk.
    assert len(fake.calls) == 1


def test_cache_persists_across_instances(tmp_path) -> None:
    fake1 = _FakeEmbeddings()
    _make(_FakeClient(fake1), cache_dir=tmp_path).embed(["x"])
    fake2 = _FakeEmbeddings()
    _make(_FakeClient(fake2), cache_dir=tmp_path).embed(["x"])
    assert fake2.calls == []


def test_duplicate_inputs_are_deduplicated_in_one_call(tmp_path) -> None:
    fake = _FakeEmbeddings()
    e = _make(_FakeClient(fake), cache_dir=tmp_path)
    out = e.embed(["same", "same", "same"])
    assert len(fake.calls) == 1
    assert fake.calls[0] == ["same"]
    # All three slots get the identical vector.
    assert out[0] == out[1] == out[2]


def test_batches_respect_batch_size(tmp_path) -> None:
    fake = _FakeEmbeddings()
    e = _make(_FakeClient(fake), cache_dir=tmp_path, batch_size=2)
    e.embed(["a", "b", "c", "d", "e"])
    # 5 unique misses with batch_size=2 -> 3 API calls of sizes [2,2,1].
    assert [len(c) for c in fake.calls] == [2, 2, 1]


def test_retries_on_transient_api_error(tmp_path) -> None:
    fake = _FakeEmbeddings(fail_times=2)
    e = _make(_FakeClient(fake), cache_dir=tmp_path)
    # Tenacity has wait_exponential(min=1) so this would normally take ~3s.
    # Override the underlying retry's wait by monkey-patching the bound method.
    from tenacity import wait_none

    e._embed_batch.retry.wait = wait_none()  # type: ignore[attr-defined]
    out = e.embed(["abc"])
    assert len(out) == 1
    # 2 failures + 1 success == 3 calls total.
    assert len(fake.calls) == 3


def test_cache_handles_corrupt_entry(tmp_path) -> None:
    cache = EmbeddingCache(tmp_path)
    key = _hash_key("foo", "model")
    cache.put(key, [1.0, 2.0])
    # Corrupt the file.
    path = tmp_path / key[:2] / f"{key}.json"
    path.write_text("not-json", encoding="utf-8")
    assert cache.get(key) is None
    assert not path.exists()


def test_disabled_cache_calls_api_every_time(tmp_path) -> None:
    fake = _FakeEmbeddings()
    e = Embedder(client=_FakeClient(fake), model="m", cache=None, batch_size=10)
    e.embed(["foo"])
    e.embed(["foo"])
    assert len(fake.calls) == 2
