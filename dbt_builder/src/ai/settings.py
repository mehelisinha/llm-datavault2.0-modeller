"""Typed configuration for the DWA AI layer.

Loads settings from environment variables (prefix ``DWA_AI_``) and an
optional ``.env`` file at the repository root. Use :func:`get_settings`
to obtain a cached singleton instance.

Example:
    >>> from dbt_builder.src.ai.settings import get_settings
    >>> cfg = get_settings()
    >>> cfg.azure_openai_endpoint
    'https://dwa-foundry-...openai.azure.com/'
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root (.env lives here, two levels up from this file's package root)
_REPO_ROOT = Path(__file__).resolve().parents[3]


class AISettings(BaseSettings):
    """Configuration for Azure AI Foundry, OpenAI, Search, and observability.

    All fields are loaded from environment variables prefixed with ``DWA_AI_``.
    A ``.env`` file at the repository root is also read if present.
    """

    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="DWA_AI_",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Azure subscription / resource metadata ────────────────────────────────
    azure_subscription_id: str = Field(..., description="Azure subscription GUID")
    azure_resource_group: str = Field(..., description="Resource group name")
    azure_region: str = Field(default="westeurope", description="Azure region")

    # ── Azure AI Foundry project ──────────────────────────────────────────────
    foundry_project_endpoint: str = Field(..., description="Foundry project endpoint URL")

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    azure_openai_endpoint: str = Field(..., description="Azure OpenAI endpoint URL")
    azure_openai_api_key: SecretStr = Field(..., description="Azure OpenAI API key")
    azure_openai_api_version: str = Field(default="2024-10-21")

    chat_deployment_gpt4o: str = Field(default="gpt-4o")
    chat_deployment_gpt5: str = Field(default="gpt-5")
    embedding_deployment: str = Field(default="text-embedding-3-small")

    # Primary chat deployment used by Phase 2 modelling agents. Defaults to
    # gpt-5 for stronger structured-reasoning quality on schema -> DV2 mapping;
    # set to ``gpt-4o`` for lower-latency, deterministic (temperature=0) runs.
    primary_chat_deployment: str = Field(default="gpt-5")

    # Dedicated chat deployment for the *modelling* agent. The modeller fans
    # out across many large prompts (one per batch) and is the hottest TPM
    # consumer in the pipeline. gpt-5 inflates each call with invisible
    # reasoning tokens *and* typically has the lowest TPM quota of any
    # deployment, which is the dominant 429 source. Defaulting this to
    # ``gpt-4o`` (deterministic, no reasoning-token overhead, usually 3-5x
    # the TPM headroom of gpt-5 in the same region) eliminates the bursty
    # 429s without touching ``primary_chat_deployment`` (still gpt-5 for
    # other agents). Override with ``DWA_AI_MODELLER_CHAT_DEPLOYMENT`` to
    # pin a specific deployment for the modeller alone.
    modeller_chat_deployment: str = Field(default="gpt-4o")

    # ── Modelling-agent token budgets ─────────────────────────────────────────
    # Per-deployment cap on completion tokens. gpt-5 spends a non-trivial share
    # of the budget on invisible reasoning tokens before emitting any visible
    # content, so larger payloads (many tables / columns) need a higher cap to
    # leave room for the JSON answer. Non-reasoning models are fine with the
    # default. Both are env-overridable so ops can raise the cap without code
    # changes when a future source system needs more headroom.
    modeller_max_tokens_default: int = Field(default=4096)
    modeller_max_tokens_gpt5: int = Field(default=16384)

    # Hard per-request ceiling on completion tokens, enforced AFTER any
    # internal budget growth (the empty-response / truncated-JSON retries
    # double the budget once). Azure rejects the call with HTTP 400
    # ``max_tokens is too large`` when the requested completion budget
    # exceeds the deployment's model limit — e.g. gpt-4o / gpt-4o-mini cap
    # completion at 16384 tokens. Doubling a 16384 budget to 32768 is what
    # crashes large-catalogue runs. This ceiling clamps every request so the
    # retry can never exceed the model maximum. Override per environment when
    # a deployment supports a higher completion limit. ``0`` disables the
    # clamp (legacy behaviour — not recommended).
    modeller_max_completion_tokens: int = Field(default=16384, ge=0)

    # Concurrency for the modelling-agent voting loop. The agent draws
    # ``samples`` independent completions and votes on the majority plan;
    # those completions are independent HTTP calls and can be issued in
    # parallel. ``0`` (the default) means "use as many workers as samples"
    # so the wall-clock latency of the analyze step collapses to a single
    # completion's RTT. Set to ``1`` to force the legacy sequential
    # behaviour (e.g. if your Azure OpenAI deployment has a tight RPM cap).
    modeller_sample_parallelism: int = Field(default=0, ge=0)

    # ── Modelling-agent table batching (large-catalog scaling) ────────────────
    # When the number of actionable tables exceeds ``modeller_batch_size``,
    # the modelling agent splits them into fixed-size batches and runs each
    # batch's completion concurrently. Batched plans are merged by name-union.
    # NOTE: links spanning two tables that land in different batches will
    # not be discovered (the modeller only sees one batch at a time). For
    # most source systems related tables cluster within the same selection
    # range so default cross-batch loss is minimal; widen ``batch_size`` to
    # reduce the risk at the cost of per-batch latency.
    # ``0`` disables batching (legacy single-prompt path).
    # Tables per batch (table-count cap). Larger batches let the modeller
    # see cross-table FK relationships in a single prompt, which is the
    # single biggest driver of link / hub quality. Lower this only if you
    # have a tight TPM quota and tolerate fragmented links.
    modeller_batch_size: int = Field(default=25, ge=0)
    # Soft cap on the estimated prompt-token count per batch. If adding the
    # next table to the current batch would push its prompt over this cap,
    # the batch is flushed early. This protects against the worst-case
    # "15 wide tables = 80k+ token prompt" scenario that single-handedly
    # exceeds the per-request TPM allowance and forces SDK retries. Setting
    # ``0`` disables the size cap (fall back to pure table-count batching).
    # Hard limit: a single batch's (prompt_tokens + completion_budget) MUST
    # stay WELL below ``llm_tokens_per_minute`` or Azure will 429 the very
    # first call AND the SDK retries will pile up against the same minute
    # window. With the default 30k TPM (Azure pay-as-you-go for gpt-4o /
    # gpt-5 in most regions) and a 2k completion budget for non-gpt5
    # deployments, 8k prompt tokens (~32k chars) leaves room for ~3 calls
    # per minute. Raise this only after you confirm a higher real quota.
    modeller_max_prompt_tokens: int = Field(default=8_000, ge=0)
    # Maximum batches to run concurrently. ``0`` means "as many as batches"
    # so total wall clock collapses to one batch's RTT. Lower this if the
    # Azure OpenAI deployment's RPM cap throttles parallel requests.
    modeller_batch_parallelism: int = Field(default=0, ge=0)
    # Samples drawn per batch when batched mode is active. Batching already
    # buys parallelism across tables; voting per batch adds cost without
    # commensurate quality. Default ``1`` keeps fan-out bounded; raise to
    # ``3`` to re-enable majority voting per batch at 3× the LLM cost.
    modeller_batch_samples: int = Field(default=1, ge=1)
    # When the table count exceeds this threshold, the modelling agent uses
    # ``samples=1`` (skips the 3-sample majority vote) to keep latency and
    # cost bounded on large catalogues. Applies to both batched and
    # single-prompt paths. ``0`` disables the threshold so voting always
    # runs at the configured sample count.
    # Large-catalogue cutoff for the 3-sample majority vote. Above this many
    # tables the modeller drops to 1 sample per batch to keep latency and
    # cost bounded. The batch mechanism already produces independent plans
    # that are merged, so per-batch voting is redundant for big catalogues.
    modeller_large_catalog_threshold: int = Field(default=15, ge=0)

    # Hard cap on **simultaneously in-flight** LLM chat-completion requests
    # made by the modelling agent across the whole process. The agent uses
    # a process-global semaphore to enforce this regardless of how many
    # batches × samples queue up. Default ``1`` serialises calls so the
    # token-bucket never has to fight two concurrent claims for the same
    # minute's quota — the safest setting for 30k-TPM pay-as-you-go
    # deployments. Raise to 2-4 only on Provisioned Throughput Units
    # (PTU) or after confirming a higher TPM with Azure.
    max_concurrent_llm_calls: int = Field(default=1, ge=1)
    # Tokens-per-minute budget for the modelling agent. Enforced by a
    # process-global token bucket that estimates each request's cost as
    # ``ceil(prompt_chars / 4) + max_completion_tokens`` and blocks until
    # the bucket has capacity. Pacing on TPM (not RPM) is what actually
    # prevents Azure 429s on large catalogues: a single 30k-token request
    # can blow a 30k/min quota by itself even when concurrency is 1.
    # Default 30_000 matches Azure's published pay-as-you-go quota for
    # gpt-4o / gpt-5 in most regions (verified June 2026). Raise only
    # after Azure portal → Foundry → Deployments → <model> → Rate Limit
    # shows a higher number.
    llm_tokens_per_minute: int = Field(default=30_000, ge=1_000)
    # SDK-level retry count for transient Azure OpenAI failures (429, 5xx).
    # The token-bucket already handles steady-state pacing; SDK retries
    # only exist to absorb sub-second bursts and occasional 5xx. Keep low
    # (3) so a quota outage surfaces fast instead of hammering Azure for
    # minutes with exponential backoff.
    llm_max_retries: int = Field(default=3, ge=0)
    # Deterministic-sampling seed passed as ``seed`` on every chat-completion
    # call (Azure OpenAI honours it for most models post-2024-05). Combined
    # with ``temperature=0`` for non-gpt5 deployments, this makes the
    # modeller, descriptor, and BV-sat proposer reproducible run-to-run on
    # an identical input — the single largest determinism lever.
    # ``-1`` disables seeding (legacy behaviour); any non-negative integer
    # turns it on. Voting samples are kept independent by adding the
    # sample index as an offset, so each sample is still distinct yet
    # individually reproducible.
    llm_seed: int = Field(default=42, ge=-1)

    # Directory holding the agent rule-prompt files (``*.md``) shared between
    # the automated pipeline agents and the manual Claude-Code agents. Empty
    # (the default) uses the in-package ``dbt_builder/src/ai/prompts`` folder
    # that ships with the wheel. Point this at an external folder (e.g. the
    # repo's loose ``dv-metadata-*.md`` skills) to override the modelling
    # rules without a code change. Missing files fall back to the built-in
    # defaults so a bad path can never crash a run.
    ai_prompts_dir: str = Field(default="")

    # Non-key technical / system columns that must never land in a satellite's
    # descriptive payload (and therefore its hashdiff): source CDC-control and
    # audit columns. Comma-separated, case-insensitive. Business keys and
    # foreign keys are stripped automatically (they belong in hubs / links), so
    # this list is only for NON-key technical columns. Empty by default and
    # fully source-agnostic; populate it with whatever control/audit column
    # names a given source carries, e.g.
    # ``DWA_AI_TECHNICAL_PAYLOAD_COLUMNS=ctl_load_flag,audit_user,audit_ts``.
    technical_payload_columns: str = Field(default="")

    def technical_payload_column_set(self) -> frozenset[str]:
        """Parsed, lower-cased set of technical payload columns to exclude."""
        return frozenset(
            token.strip().lower()
            for token in self.technical_payload_columns.split(",")
            if token.strip()
        )

    # ── Plan reviewer (two-model generate → review) ───────────────────────────
    # A second, stronger model critiques and patches the modelling plan AFTER
    # the (fast) generator produces it and BEFORE the deterministic emitter
    # renders it. The generator runs many batched calls so it must be fast and
    # cheap (default gpt-4.1); the reviewer runs ONE call per run, so it can be
    # the strongest available model with negligible cost/latency impact
    # (e.g. gpt-5.2). Review happens at the plan (JSON) level, so the emitter
    # stays deterministic and the output byte-stable. Default OFF so the
    # existing single-model flow is unchanged until explicitly enabled.
    plan_review_enabled: bool = Field(default=False)
    # Deployment used by the reviewer. Empty + enabled is a misconfiguration
    # (the reviewer is skipped with a warning rather than crashing the run).
    plan_reviewer_chat_deployment: str = Field(default="")
    # Output budget for the reviewer's corrected-plan reply. The reviewer emits
    # the full plan, so this must fit the plan JSON; for very large catalogues
    # raise it (gpt-5-family deployments allow large completions) or the review
    # truncates and the run safely falls back to the un-reviewed plan.
    plan_reviewer_max_tokens: int = Field(default=32768, ge=1)
    # Above this many hubs, the reviewer reviews the plan in per-hub-group
    # chunks instead of one whole-plan call. A single call over a large plan
    # tempts the model to "tidy up" by merging entities away (a collapse the
    # guard then rejects, wasting the call); chunked review keeps each slice
    # small enough to refine rather than collapse. ``0`` disables chunking.
    plan_review_chunk_size: int = Field(default=12, ge=0)
    # Max concurrent chunk reviews when a large plan is reviewed in chunks. The
    # chunk reviews are independent LLM calls, so running them concurrently keeps
    # the wall-clock close to a single call instead of summing them. ``0`` means
    # "one worker per chunk" (fully concurrent); set a positive value to cap
    # fan-out if the reviewer deployment rate-limits (429s). ``1`` = sequential.
    plan_review_parallelism: int = Field(default=0, ge=0)

    # Opt-in flag for the DV2 Planning Agent (a richer pre-step that emits
    # hub/link/satellite-split decisions, BV proposals, PIT volume
    # estimates, and human-review flags as one structured JSON document).
    # Default off so the existing pipeline path is byte-identical until
    # the orchestrator wiring lands in a follow-up. When enabled, the
    # agent is invoked at the start of ANALYZE.
    planning_agent_enabled: bool = Field(default=False)

    # ── dbt compile gate (Step 6 hard validation) ────────────────────────────
    # When enabled, the validator materialises the generated plan into the
    # configured dbt project and runs ``dbt parse`` → ``dbt compile`` (and
    # ``dbt build`` when ``dbt_build_enabled``). Any dbt failure becomes an
    # ERROR issue, which the approval gate treats as blocking — so nothing is
    # approvable/exportable unless it actually compiles. Default OFF so offline
    # runs/tests are unchanged; the project must have AutomateDV installed
    # (``dbt deps``) and a usable profile. ``dbt_project_dir`` is the dbt
    # project root the generated models are written into and built from.
    dbt_validation_enabled: bool = Field(default=False)
    dbt_project_dir: str = Field(default="")
    dbt_build_enabled: bool = Field(default=False)

    # ── Business-vault satellite proposer (LlmBvSatProposer) ──────────────────
    # Opt-in third LLM touchpoint: after the raw-vault plan is built, propose
    # derived / business-rule satellites (classification, normalisation,
    # enrichment) gated by deterministic pattern detection. Default OFF so the
    # pipeline's LLM usage is unchanged until explicitly enabled. One extra call
    # per run. Deployment defaults to the modeller's (per user decision).
    bv_sats_enabled: bool = Field(default=False)
    bv_sat_chat_deployment: str = Field(default="")
    bv_sat_max_tokens: int = Field(default=2000, ge=1)

    # Concurrency for per-table ``DESCRIBE TABLE`` calls during bronze /
    # vault snapshotting. Each call is an independent Databricks REST or
    # Spark SQL round-trip; running them serially produces an N+1 latency
    # cliff on wide schemas. ``1`` forces serial behaviour for debugging.
    catalog_describe_parallelism: int = Field(default=8, ge=1)

    # ── Vector backend (Phase 2) ──────────────────────────────────────────────
    # 'faiss' is the default for offline / dev work and unit tests; 'azure'
    # uses Azure AI Search (any SKU) when ``search_endpoint`` is configured.
    vector_backend: str = Field(default="faiss")
    vector_cache_dir: str = Field(
        default=".cache/ai",
        description="Directory for FAISS index files and embedding cache (gitignored).",
    )

    # ── Azure AI Search (optional in Phase 0/1; required from Phase 2 onward) ─
    search_endpoint: str | None = Field(default=None, description="Azure AI Search endpoint URL")
    search_admin_key: SecretStr | None = Field(default=None, description="Admin API key")
    search_index_patterns: str = Field(default="dv-patterns")
    search_index_decisions: str = Field(default="approved-decisions")

    # ── YAML Metadata store (ADLS Gen2) ──────────────────────────────────────
    # Set DWA_AI_METADATA_STORE_ACCOUNT to enable ADLS Gen2-backed storage.
    # When unset the service falls back to LocalYamlStore (.cache/approved_yamls/).
    metadata_store_account: str | None = Field(
        default=None,
        description=(
            "ADLS Gen2 storage account name (without .dfs.core.windows.net). "
            "Leave blank to use the local filesystem store in dev/CI."
        ),
    )
    metadata_store_container: str = Field(
        default="dwa-metadata",
        description="Container / filesystem name within the storage account.",
    )
    metadata_store_sp_client_id: str | None = Field(
        default=None,
        description="Service principal client ID for ADLS Gen2 read/write access.",
    )
    metadata_store_sp_client_secret: SecretStr | None = Field(
        default=None,
        description="Service principal client secret for ADLS Gen2 read/write access.",
    )
    metadata_store_tenant_id: str | None = Field(
        default=None,
        description="Azure AD tenant ID for the ADLS Gen2 service principal.",
    )

    # ── Observability ─────────────────────────────────────────────────────────
    appinsights_connection_string: SecretStr | None = Field(default=None)

    def modeller_max_tokens_for(self, deployment: str) -> int:
        """Return the modelling-agent token budget for ``deployment``.

        gpt-5-family deployments use ``modeller_max_tokens_gpt5`` (default
        16384) to absorb the invisible reasoning-token overhead; everything
        else uses ``modeller_max_tokens_default`` (default 4096).
        """
        if deployment.startswith("gpt-5"):
            return self.modeller_max_tokens_gpt5
        return self.modeller_max_tokens_default

    def modeller_completion_cap(self) -> int:
        """Return the hard ceiling on per-request completion tokens.

        Used by the modelling agent to clamp the (possibly doubled) token
        budget so a retry can never exceed the deployment's model limit and
        trigger an Azure HTTP 400. ``0`` means "no clamp".
        """
        return self.modeller_max_completion_tokens


@lru_cache(maxsize=1)
def get_settings() -> AISettings:
    """Return a cached :class:`AISettings` instance."""
    return AISettings()  # type: ignore[call-arg]
