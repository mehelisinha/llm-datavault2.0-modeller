"""Embedding client with on-disk cache and exponential-backoff retry.

Wraps the Azure OpenAI ``embeddings.create`` endpoint so callers get:

* **Determinism + cost control via cache** — embeddings for a given
  ``(text, model_name)`` pair are content-addressed (sha256) and persisted
  under ``settings.vector_cache_dir / "embeddings"``. Re-embedding the same
  column description across runs is free.
* **Resilience** — transient Azure errors (rate limits, 5xx, timeouts)
  retry with tenacity exponential backoff up to 5 attempts.
* **Batching** — Azure OpenAI accepts up to 2048 inputs per request; we
  send everything that misses the cache in batches of ``batch_size``.

The embedder does not know about FAISS or Azure Search; it just returns
``list[tuple[float, ...]]`` aligned to the input order. The caller wraps
those in :class:`VectorRecord` and writes to a :class:`VectorStore`.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import AISettings


# Azure OpenAI default for text-embedding-3-small. Override per call only if a
# different model with a different limit is wired in.
_DEFAULT_BATCH_SIZE = 256

_RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, APIError)


def _hash_key(text: str, model: str) -> str:
    """Stable cache key for a (text, model) pair."""
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


class EmbeddingCache:
    """Simple JSON-file disk cache: one file per ``(text, model)`` pair.

    Files are sharded into 256 sub-directories by the first byte of the hash
    so a single dir never gets unwieldy on Windows. Files are tiny (~10 KB
    for a 1536-dim vector serialised as JSON).
    """

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        return self._root / key[:2] / f"{key}.json"

    def get(self, key: str) -> tuple[float, ...] | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            return tuple(float(x) for x in payload["vector"])
        except (OSError, ValueError, KeyError):
            # Corrupt cache entry: drop it so the next call re-embeds.
            path.unlink(missing_ok=True)
            return None

    def put(self, key: str, vector: Sequence[float]) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write; embedding files are read by other processes.
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump({"vector": list(vector)}, fh)
        os.replace(tmp, path)


class Embedder:
    """Cached, retrying wrapper around Azure OpenAI embeddings.

    Parameters
    ----------
    client
        Pre-built :class:`openai.AzureOpenAI` instance. Constructed lazily
        in :func:`get_embedder` from settings.
    model
        Deployment name (e.g. ``text-embedding-3-small``).
    cache
        Optional :class:`EmbeddingCache`. Pass ``None`` to disable caching
        (useful only in tests; production paths should always cache).
    batch_size
        Maximum inputs per Azure request.
    """

    def __init__(
        self,
        *,
        client: AzureOpenAI,
        model: str,
        cache: EmbeddingCache | None,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self._client = client
        self._model = model
        self._cache = cache
        self._batch_size = batch_size

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: Iterable[str]) -> list[tuple[float, ...]]:
        """Return embeddings aligned to ``texts`` (cache + batched API calls).

        Empty strings are passed through to Azure unchanged (the API accepts
        them and returns a zero-ish vector); duplicate strings within the
        same call are de-duplicated so we only pay once per unique text.
        """
        text_list = list(texts)
        n = len(text_list)
        results: list[tuple[float, ...] | None] = [None] * n

        # Stage 1: cache hits.
        misses_by_text: dict[str, list[int]] = {}
        for i, text in enumerate(text_list):
            key = _hash_key(text, self._model)
            cached = self._cache.get(key) if self._cache is not None else None
            if cached is not None:
                results[i] = cached
            else:
                misses_by_text.setdefault(text, []).append(i)

        # Stage 2: batched API calls for unique misses.
        unique_misses = list(misses_by_text.keys())
        for start in range(0, len(unique_misses), self._batch_size):
            batch = unique_misses[start : start + self._batch_size]
            vectors = self._embed_batch(batch)
            for text, vector in zip(batch, vectors, strict=True):
                vec_tuple = tuple(float(x) for x in vector)
                if self._cache is not None:
                    self._cache.put(_hash_key(text, self._model), vec_tuple)
                for idx in misses_by_text[text]:
                    results[idx] = vec_tuple

        # All slots must be filled at this point.
        return [v if v is not None else () for v in results]

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _embed_batch(self, batch: Sequence[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._model, input=list(batch))
        # Azure returns items in the same order as the input list per docs.
        return [list(item.embedding) for item in response.data]


def get_embedder(
    *,
    settings: AISettings | None = None,
    model: str | None = None,
    use_cache: bool = True,
) -> Embedder:
    """Build an :class:`Embedder` from settings (cached on disk by default)."""
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import get_settings

    cfg = settings or get_settings()
    chosen_model = model or cfg.embedding_deployment
    client = AzureOpenAI(
        azure_endpoint=cfg.azure_openai_endpoint,
        api_key=cfg.azure_openai_api_key.get_secret_value(),
        api_version=cfg.azure_openai_api_version,
    )
    cache = EmbeddingCache(Path(cfg.vector_cache_dir) / "embeddings") if use_cache else None
    return Embedder(client=client, model=chosen_model, cache=cache)
