"""DWA AI layer — metadata-driven Data Vault assistance.

Subpackages (added incrementally per phase):
    settings        — typed configuration loader (pydantic-settings)
    hello_foundry   — Phase 0 smoke test
    contracts/      — Pydantic payloads & decision models (Phase 1)
    discovery/      — deterministic source-schema discovery (Phase 1)
    llm/            — Foundry client wrappers (Phase 2)
    rag/            — Azure AI Search retrieval (Phase 2)
"""

__all__: list[str] = []
