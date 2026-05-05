"""Opt-in live tests against real Azure resources.

Run with::

    .venv\\Scripts\\python.exe -m pytest tests/ai/test_live.py --live -q

Costs (approximate, per full run):
    embedding   ~ EUR 0.001  (2 short strings, text-embedding-3-small)
    chat call   ~ EUR 0.05   (one gpt-5 propose() against a 1-table payload)
    search      EUR 0.00     (F1 free tier)

Skipped automatically when ``--live`` is not passed (see conftest.py).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.ai, pytest.mark.live]

from dbt_builder.src.ai.contracts.payloads import (  # noqa: E402
    DiscoveryPayload,
    InferredType,
    SourceColumn,
    SourceSystem,
    SourceTable,
)
from dbt_builder.src.ai.embeddings import (  # noqa: E402
    VectorRecord,
    get_embedder,
    get_vector_store,
)
from dbt_builder.src.ai.settings import get_settings  # noqa: E402


def _tiny_payload() -> DiscoveryPayload:
    return DiscoveryPayload(
        system=SourceSystem(
            system_id="iec_cim",
            system_name="IEC61968_CIM",
            source_type="delta",
        ),
        tables=(
            SourceTable(
                name="conducting_equipment",
                columns=(
                    SourceColumn(
                        name="mrid",
                        raw_dtype="varchar(64)",
                        inferred_type=InferredType.STRING,
                        nullable=False,
                    ),
                    SourceColumn(
                        name="name",
                        raw_dtype="varchar(255)",
                        inferred_type=InferredType.STRING,
                    ),
                    SourceColumn(
                        name="equipment_type",
                        raw_dtype="varchar(64)",
                        inferred_type=InferredType.STRING,
                    ),
                ),
            ),
        ),
    )


def test_live_embedding_round_trip(tmp_path) -> None:
    """Embedding -> FAISS upsert -> search returns the embedded text on top."""
    cfg = get_settings()
    embedder = get_embedder(settings=cfg, use_cache=False)
    vectors = embedder.embed(["Data Vault hub for conducting equipment", "weather forecast"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 1536  # text-embedding-3-small dimension

    store = get_vector_store("dwa-live-smoke", dimension=1536, settings=cfg, backend="faiss")
    # Use tmp_path for the cache so we never pollute the real cache dir.
    from dbt_builder.src.ai.embeddings.faiss_store import FaissVectorStore

    store = FaissVectorStore(
        index_name="dwa-live-smoke",
        dimension=1536,
        cache_dir=tmp_path,
    )
    store.upsert(
        [
            VectorRecord(id="ce", vector=vectors[0], metadata={"topic": "dv"}),
            VectorRecord(id="weather", vector=vectors[1], metadata={"topic": "noise"}),
        ]
    )
    hits = store.search(vectors[0], top_k=2)
    assert hits[0].id == "ce"
    assert hits[0].score > hits[1].score


def test_live_search_index_listing() -> None:
    """F1 Azure AI Search service is reachable with our admin key."""
    cfg = get_settings()
    if not cfg.search_endpoint or cfg.search_admin_key is None:
        pytest.skip("DWA_AI_SEARCH_ENDPOINT / DWA_AI_SEARCH_ADMIN_KEY not configured")
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient

    client = SearchIndexClient(
        cfg.search_endpoint,
        AzureKeyCredential(cfg.search_admin_key.get_secret_value()),
    )
    # We don't assert on contents (the F1 tier may be empty); reaching the
    # endpoint without an exception is the contract.
    list(client.list_index_names())


def test_live_modeller_proposes_at_least_one_hub_with_default_model() -> None:
    """End-to-end: real chat call returns a valid plan with >=1 hub."""
    from dbt_builder.src.ai.agents import get_modelling_agent

    cfg = get_settings()
    # samples=1 keeps the cost minimal for the smoke check; the gpt-5 vs
    # gpt-4o eval (test_eval_*) uses larger samples.
    agent = get_modelling_agent(settings=cfg, samples=1, max_tokens=2048)
    plan = agent.propose(_tiny_payload())
    assert plan.system_id == "iec_cim"
    assert len(plan.hubs) >= 1
    assert plan.hubs[0].source_table == "conducting_equipment"
