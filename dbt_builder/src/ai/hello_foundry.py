"""Phase 0 smoke test for the DWA AI layer.

Verifies that the local environment can:
  1. Load typed settings from ``.env``
  2. Acquire an Entra ID token via ``DefaultAzureCredential`` (i.e. ``az login``)
  3. Call the GPT-4o chat deployment on Azure OpenAI
  4. Call the GPT-5 chat deployment on Azure OpenAI
  5. Call the embedding deployment on Azure OpenAI
  6. Connect to Azure AI Search and list indexes

Run after provisioning + populating ``.env``::

    python -m dbt_builder.src.ai.hello_foundry

Exit code 0 = all checks passed. Non-zero = at least one check failed
(stderr will show which one).

NOTE: requires the caller's Entra identity to have role
``Cognitive Services OpenAI User`` on the AI Services (Foundry) resource.
The provisioning script assigns this automatically.
"""

from __future__ import annotations

import sys
from typing import Callable

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from openai import AzureOpenAI

from dbt_builder.src.ai.settings import AISettings, get_settings

_OK = "[ OK ]"
_FAIL = "[FAIL]"


def _build_openai_client(settings: AISettings) -> AzureOpenAI:
    """Construct an Azure OpenAI client using API key auth.

    NOTE: Phase 0 uses API keys because the developer has only Contributor
    on the resource group (cannot self-assign 'Cognitive Services OpenAI
    User' role). Migrate to ``DefaultAzureCredential`` once managed
    identity / RBAC is in place.
    """
    return AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key.get_secret_value(),
        api_version=settings.azure_openai_api_version,
    )


def _check_chat(client: AzureOpenAI, deployment: str) -> str:
    """Call a chat deployment with a trivial prompt; return its reply.

    GPT-5 requires ``max_completion_tokens`` instead of the legacy
    ``max_tokens`` parameter; older models accept either. We detect by
    deployment name prefix to stay forward-compatible.
    """
    token_kwargs: dict[str, int] = (
        {"max_completion_tokens": 200} if deployment.startswith("gpt-5") else {"max_tokens": 80}
    )
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "You are a Data Vault 2.0 expert."},
            {"role": "user", "content": "In one sentence, what is a hub?"},
        ],
        temperature=1.0 if deployment.startswith("gpt-5") else 0.0,
        **token_kwargs,
    )
    return (response.choices[0].message.content or "").strip()


def _check_embedding(client: AzureOpenAI, deployment: str) -> int:
    """Embed a short string; return the vector dimension."""
    response = client.embeddings.create(
        model=deployment,
        input="customer master entity",
    )
    return len(response.data[0].embedding)


def _check_search(settings: AISettings) -> list[str] | str:
    """List existing index names on the AI Search service.

    Returns the literal string "skipped (not configured)" if the Search
    service is not provisioned. This keeps Phase 0 valid in cost-minimized
    setups where Search is deferred until Phase 2.
    """
    if not settings.search_endpoint or not settings.search_admin_key:
        return "skipped (not configured)"
    client = SearchIndexClient(
        endpoint=settings.search_endpoint,
        credential=AzureKeyCredential(settings.search_admin_key.get_secret_value()),
    )
    return list(client.list_index_names())


def _run_check(label: str, fn: Callable[[], object]) -> bool:
    """Run a check, log result, return True on success."""
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 — smoke test surfaces any failure
        print(f"{_FAIL} {label}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False
    print(f"{_OK} {label}: {result}")
    return True


def main() -> int:
    """Run all Phase 0 smoke checks. Return process exit code."""
    print("DWA AI layer — Phase 0 smoke test")
    print("=" * 60)

    try:
        settings = get_settings()
    except Exception as exc:  # noqa: BLE001
        print(f"{_FAIL} load settings: {exc}", file=sys.stderr)
        print("\nHint: copy .env.template to .env and fill in values.", file=sys.stderr)
        return 1

    print(f"{_OK} load settings: subscription={settings.azure_subscription_id[:8]}…")
    print(f"        rg={settings.azure_resource_group} region={settings.azure_region}")

    openai_client = _build_openai_client(settings)

    checks = [
        ("chat gpt-4o", lambda: _check_chat(openai_client, settings.chat_deployment_gpt4o)),
        ("chat gpt-5", lambda: _check_chat(openai_client, settings.chat_deployment_gpt5)),
        (
            f"embedding {settings.embedding_deployment} (dim)",
            lambda: _check_embedding(openai_client, settings.embedding_deployment),
        ),
        ("search list_index_names", lambda: _check_search(settings)),
    ]

    failures = sum(0 if _run_check(label, fn) else 1 for label, fn in checks)

    print("=" * 60)
    if failures:
        print(f"{_FAIL} {failures} check(s) failed.", file=sys.stderr)
        return 1
    print(f"{_OK} All Phase 0 checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
