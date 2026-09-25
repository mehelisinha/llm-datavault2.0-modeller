"""Deterministic reference-YAML loader (RAG replacement).

This package replaces the FAISS / Azure-AI-Search retrieval pipeline that
previously sat in :mod:`dbt_builder.src.ai.embeddings`. The new design:

* **No embeddings, no network calls, no caches.** A directory of approved
  raw-vault YAML files (typically ``models/raw_vault/``) is loaded once
  per process and held in memory.
* **Relevance is lexical.** Selection uses token overlap on the *target
  table name* against each reference example's *source name and tags*.
  The prompt block is therefore reproducible across runs (same input ->
  byte-identical output), which is a property RAG could never give us.
* **Typed contracts.** Reference examples are :class:`ReferenceExample`
  instances; the agents never see raw dicts or YAML strings.

The public surface is intentionally small:

* :class:`ReferenceLoader` — load a directory tree into typed examples.
* :class:`ReferenceExample` — one hub / sat / link reference.
* :func:`get_default_loader` — process-wide cached loader pointing at the
  repo's ``models/raw_vault`` directory.
"""

from __future__ import annotations

from dbt_builder.src.ai.reference.loader import (
    ReferenceExample,
    ReferenceKind,
    ReferenceLoader,
    get_default_loader,
)

__all__ = [
    "ReferenceExample",
    "ReferenceKind",
    "ReferenceLoader",
    "get_default_loader",
]
