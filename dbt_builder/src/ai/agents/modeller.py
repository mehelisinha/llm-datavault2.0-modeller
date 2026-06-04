"""LLM modelling agent that proposes a Data Vault 2 plan from discovery.

Pipeline (single ``propose`` call):

1. **Compact the payload** into a JSON-friendly prompt that fits the chat
   context. Only the fields the model actually needs are sent (column name,
   type, sample values, key signal); raw dtypes and large samples are
   summarised.
2. **Sample n times** (default 3) from the chat completion endpoint with
   model-appropriate parameters:

   * gpt-5 family: ``temperature=1.0`` (only value gpt-5 accepts) and
     ``max_completion_tokens``. Empty-content responses (a known gpt-5
     intermittent failure mode) are retried with a doubled token budget.
   * Other models (gpt-4o, gpt-4-turbo, ...): ``temperature=0.0`` and
     ``max_tokens``. ``response_format={"type": "json_object"}`` is requested
     when the SDK supports it so output is always valid JSON.

3. **Validate each sample** against :class:`ModelingPlan`. Invalid samples
   are dropped (Phase 2 keeps it simple — we let the voting step pick a
   winner from the valid candidates rather than re-prompting on each fail,
   which would multiply latency and cost without measurable quality lift).
4. **Vote** across valid plans by entity-fingerprint majority. The winner
   is the plan whose ``(sorted hub names, sorted link names, sorted sat
   names)`` fingerprint occurs most often; ties are broken by highest
   total confidence then by lowest index.

If no sample yields a valid plan, a :class:`ModellingAgentError` is raised
with the validation errors from each attempt so the caller can surface a
useful failure message rather than re-running silently.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Condition, Lock
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from dbt_builder.src.ai.agents.sat_split_heuristics import build_hint as build_sat_split_hint
from dbt_builder.src.ai.agents.tool_loop import (
    ToolLoopError,
    ToolSpec,
    run_tool_loop,
)
from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    HubDecision,
    LinkDecision,
    ModelingPlan,
    SatelliteDecision,
)
from dbt_builder.src.ai.contracts.payloads import (
    DiscoveryPayload,
    SourceColumn,
    SourceTable,
)

if TYPE_CHECKING:
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import AISettings

_LOG = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a senior Data Vault 2.0 modelling expert applying Dan Linstedt's "
    "classical conventions. You receive a JSON description of a source system "
    "(tables and their columns, including descriptions, samples, cardinality, "
    "null-rate, and key signals) and propose a raw-vault model: HUBS, LINKS, "
    "and SATELLITES. Be thorough — under-modelling links and multi-hub tables "
    "is the most common mistake and must be avoided.\n\n"
    "MANDATORY RULES:\n"
    "1. BUSINESS-KEY SELECTION. Choose a real, human-meaningful business key "
    "whenever the table has one (e.g. `iso3166_3` for a country, `user`+`group` "
    "for a membership table, `task` for a task reference). Only fall back to "
    "`sys_id` / `id` / GUID-like surrogates when no semantic key exists. "
    "High-cardinality NOT-NULL columns with low null_rate and high "
    "cardinality_ratio that are NOT GUIDs are your candidates.\n"
    "2. MULTI-HUB DECOMPOSITION. A single source table OFTEN yields MORE THAN "
    "ONE HUB. Any table whose primary purpose is to associate two entities "
    "(e.g. `sys_user_grmember` has `user` and `group`; `task_sla` has `task` "
    "and `sla`) MUST produce one hub per referenced entity (`hub_user`, "
    "`hub_group`) PLUS a link joining them (`link_user_group`). Do not collapse "
    "such tables into a single `sys_id` hub.\n"
    "3. LINK GENERATION IS REQUIRED. For EVERY table you process, scan all "
    "columns for FK-like references (columns named like `<entity>`, "
    "`<entity>_id`, `parent`, `manager`, `owner`, `contact`, `company`, "
    "`group`, `user`, `department`, `location`, `country`, `vendor`, "
    "`assigned_to`, `caller_id`, etc., or columns whose samples are GUIDs "
    "pointing at another hub). EACH such FK column produces a link "
    "(`link_<src>_<target>`) with two hash keys. Tables with ZERO links are "
    "extremely rare — only pure reference tables (e.g. country code lookup) "
    "have none. NEVER return an empty `links: []` list when the catalog has "
    "association tables.\n"
    "4. SELF-REFERENCING LINKS. Hierarchy columns (`parent`, `manager`, "
    "`reports_to`) produce a self-link with `HK_<HUB>_CHILD` and "
    "`HK_<HUB>_PARENT` FKs.\n"
    "5. EFFECTIVITY SATELLITES. For EVERY link you create, also create an "
    "`eff_sat_<link_name>` with `driving_fk` set to the primary side and "
    "`secondary_fk` listing the other side(s).\n"
    "6. DESCRIPTIVE SATELLITES (BLUEPRINT-DRIVEN). For EVERY table you "
    "process, the user prompt's `sat_split_hint[<source_table>]` block "
    "contains a `satellites_to_emit` array. Each entry IS a 1:1 blueprint "
    "for one satellite to emit, with `subgroup`, `change_velocity`, and "
    "`payload` already filled in. You MUST emit EXACTLY one satellite per "
    "blueprint entry — no more, no less — copying `subgroup`, "
    "`change_velocity`, and `payload` verbatim. Name them `sat_<hub>` when "
    "`subgroup` is null, otherwise `sat_<hub>_<subgroup>` (e.g. "
    "`sat_<hub>_details`). Set `hashdiff` to `HD_<CONCEPT>` when "
    "`subgroup` is null, otherwise `HD_<CONCEPT>_<SUBGROUP>` (uppercase). "
    "Each hub receives between 1 and 3 satellites — never more. Do NOT "
    "add any field to a satellite that is not in the satellite schema "
    "shown below (no `operational`, `measurements`, or any other extra "
    "key — only the listed fields).\n"
    "7. NAMING. snake_case with prefixes `hub_`, `link_`, `sat_`, `eff_sat_`. "
    "Hash keys UPPER_SNAKE prefixed `HK_`. Hash-diffs prefixed `HD_`.\n"
    "8. CROSS-BATCH AWARENESS. You may be processing only a subset of the "
    "full catalog. Still emit links/hubs for any entity referenced by the "
    "tables in front of you — downstream consolidation will deduplicate.\n"
    "9. BARE SOURCE-TABLE NAMES. The `source_table` field on every hub, "
    "link, and satellite MUST be the bare table name (no `catalog.schema.` "
    "prefix). Downstream renderers compose staging-model names as "
    "`stg_<source_table>` and break on qualifiers.\n\n"
    "OUTPUT FORMAT: Return STRICT JSON matching the provided schema. No prose, "
    "no markdown, no commentary outside the JSON object."
)

# Confidence string -> ordinal weight for tie-breaking.
_CONFIDENCE_WEIGHT = {
    DecisionConfidence.LOW: 1,
    DecisionConfidence.MEDIUM: 2,
    DecisionConfidence.HIGH: 3,
}

# Cap how much of each column's profile we ship to keep prompts compact.
_MAX_SAMPLE_VALUES_PER_COLUMN = 3
_MAX_TABLES_IN_PROMPT = 50
# When a table has more than this many columns it is considered "wide" and
# its prompt representation is compressed: long free-text values are skipped
# but the modeller still receives every column's name, type, and the key /
# cardinality signals it needs to (a) pick a real business key over a
# surrogate GUID and (b) detect FK relationships across tables. Dropping
# those signals collapses the plan quality drastically (hubs default to
# table names, FK columns degenerate to self-references), which is far
# worse than spending a few extra tokens.
_WIDE_TABLE_COLUMN_THRESHOLD = 40
# Per-column maximum length for free-text fields (description, individual
# sample value) sent to the model in wide-table mode. Long ServiceNow /
# SAP description blobs are summarised at this length; column names,
# types, and key signals are always preserved in full.
_WIDE_TABLE_TEXT_TRUNCATE = 80


# ----- Process-global Azure OpenAI rate limiting ---------------------------
# Two coordinated gates protect against quota exhaustion:
#
# 1. ``_LLM_SEMAPHORE`` bounds *simultaneously in-flight* requests (RPM-ish).
# 2. ``_LLM_TOKEN_BUCKET`` bounds *tokens consumed per minute* (TPM).
#
# Azure OpenAI returns 429 when either limit is exceeded. Real workloads with
# uneven prompt sizes hit TPM first (e.g. 4 × 80k-token requests = 320k
# tokens/min against a 60k/min deployment), so a request-count semaphore on
# its own is insufficient. Both gates are initialised lazily from settings
# on first use and fall back to permissive values when settings cannot be
# loaded (e.g. unit tests with no env).
_LLM_SEMAPHORE: BoundedSemaphore | None = None
_LLM_SEMAPHORE_LOCK = Lock()

# Rough character-to-token ratio used to estimate prompt cost without
# pulling in a tokenizer dependency. 4 chars/token is the documented OpenAI
# heuristic for English-heavy JSON payloads and is conservative enough that
# the token bucket never under-counts in practice.
_CHARS_PER_TOKEN = 4


class _TokenBucket:
    """Thread-safe token bucket used to pace Azure OpenAI calls by TPM.

    ``capacity`` is the max burst (one minute's worth of tokens). ``refill``
    is tokens-per-second. ``acquire(n)`` blocks until ``n`` tokens are
    available, then deducts them. Requests larger than ``capacity`` are
    clamped to ``capacity`` so a single oversized call cannot deadlock the
    bucket; the bucket then has to refill from empty before the next call
    runs, which is the desired self-throttling behaviour.
    """

    def __init__(self, *, capacity: float, refill_per_sec: float) -> None:
        self._capacity = float(capacity)
        self._refill = float(refill_per_sec)
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._cv = Condition()

    def acquire(self, n: float) -> None:
        n = max(n, 0.0)
        # Oversized requests (single call cost > one minute's quota) cannot
        # be served honestly. Clamping them silently — the previous behaviour
        # — lets the SDK fire the request and immediately get 429'd by Azure
        # because the *actual* per-minute consumption exceeds quota. Instead
        # we wait until the bucket is fully refilled and then drain it; this
        # forces sequencing (one oversized call per minute) and emits a clear
        # warning so the operator knows to either lower max_prompt_tokens or
        # raise the deployment's TPM.
        if n > self._capacity:
            _LOG.warning(
                "LLM call estimated at %.0f tokens exceeds per-minute bucket "
                "capacity %.0f — forcing serial pacing. Lower modeller_max_"
                "prompt_tokens or raise llm_tokens_per_minute.",
                n,
                self._capacity,
            )
            n = self._capacity
            with self._cv:
                while True:
                    now = time.monotonic()
                    self._tokens = min(
                        self._capacity,
                        self._tokens + (now - self._last_refill) * self._refill,
                    )
                    self._last_refill = now
                    if self._tokens >= self._capacity - 1e-6:
                        self._tokens = 0.0
                        return
                    wait = (self._capacity - self._tokens) / self._refill
                    self._cv.wait(timeout=max(wait, 0.05))
        with self._cv:
            while True:
                now = time.monotonic()
                self._tokens = min(
                    self._capacity,
                    self._tokens + (now - self._last_refill) * self._refill,
                )
                self._last_refill = now
                if self._tokens >= n:
                    self._tokens -= n
                    return
                # Sleep just long enough to accumulate the missing tokens,
                # then re-check. Condition.wait releases the lock so other
                # callers can also try (one will win the next refill).
                missing = n - self._tokens
                wait = missing / self._refill if self._refill > 0 else 0.05
                self._cv.wait(timeout=max(wait, 0.05))


_LLM_TOKEN_BUCKET: _TokenBucket | None = None
_LLM_TOKEN_BUCKET_LOCK = Lock()


def _get_llm_semaphore() -> BoundedSemaphore:
    """Return the process-global RPM gate, building it from settings on first call."""
    global _LLM_SEMAPHORE
    if _LLM_SEMAPHORE is not None:
        return _LLM_SEMAPHORE
    with _LLM_SEMAPHORE_LOCK:
        if _LLM_SEMAPHORE is None:
            try:
                from dbt_builder.src.ai.settings import get_settings

                permits = get_settings().max_concurrent_llm_calls
            except Exception:
                permits = 16
            _LLM_SEMAPHORE = BoundedSemaphore(value=permits)
            _LOG.info("ModellingAgent LLM concurrency gate initialised with %d permit(s)", permits)
        return _LLM_SEMAPHORE


def _get_llm_token_bucket() -> _TokenBucket:
    """Return the process-global TPM bucket, building it from settings on first call.

    Falls back to a very large bucket (effectively no throttling) when
    settings cannot be loaded so unit tests are unaffected.
    """
    global _LLM_TOKEN_BUCKET
    if _LLM_TOKEN_BUCKET is not None:
        return _LLM_TOKEN_BUCKET
    with _LLM_TOKEN_BUCKET_LOCK:
        if _LLM_TOKEN_BUCKET is None:
            try:
                from dbt_builder.src.ai.settings import get_settings

                tpm = get_settings().llm_tokens_per_minute
            except Exception:
                tpm = 10_000_000  # effectively unbounded for tests
            _LLM_TOKEN_BUCKET = _TokenBucket(
                capacity=float(tpm), refill_per_sec=float(tpm) / 60.0
            )
            _LOG.info(
                "ModellingAgent LLM token bucket initialised: %d tokens/min (~%.0f tokens/sec)",
                tpm,
                float(tpm) / 60.0,
            )
        return _LLM_TOKEN_BUCKET


def _estimate_call_tokens(messages: Sequence[dict[str, Any]], kwargs: dict[str, Any]) -> int:
    """Estimate total tokens a chat call will consume against the TPM quota.

    Azure counts both prompt and completion tokens. We estimate the prompt
    from ``len(json.dumps(messages)) / 4`` (the standard OpenAI heuristic)
    and assume the completion uses its full budget so we under-throttle
    only when the model returns short answers (safe direction).
    """
    try:
        prompt_chars = sum(len(m.get("content") or "") for m in messages)
    except Exception:
        prompt_chars = 0
    prompt_tokens = math.ceil(prompt_chars / _CHARS_PER_TOKEN)
    completion_budget = int(
        kwargs.get("max_completion_tokens") or kwargs.get("max_tokens") or 0
    )
    return prompt_tokens + completion_budget


# Decision models whose declared field set we use to strip LLM-emitted
# extras before pydantic validation. The mapping is sourced from
# ``model_fields`` at runtime so adding a field to any decision model
# (or removing one) is automatically picked up here — nothing to update.
_DECISION_MODEL_BY_KEY: dict[str, type[Any]] = {
    "hubs": HubDecision,
    "links": LinkDecision,
    "satellites": SatelliteDecision,
}

# Cardinality ratio above which a column is treated as a candidate key when
# no explicit ``is_likely_key`` flag is set. Matches the threshold used by
# the satellite-split heuristics so the two analyses are consistent.
_SYNTH_KEY_CARDINALITY = 0.95
# Hard cap on how many business-key columns we synthesise per missing hub —
# keeps composite keys from exploding when many columns look key-like.
_SYNTH_MAX_BUSINESS_KEYS = 2


def _build_synthesis_hints(
    tables: Iterable[SourceTable],
) -> dict[str, dict[str, Any]]:
    """Pre-compute hub-synthesis hints from discovery, keyed by source table.

    Each hint carries the data needed to materialise a minimum-valid
    :class:`HubDecision` when the LLM forgets to emit one: derived
    business keys (likely-key columns), and a deterministic hash-key
    name. Reading these from the discovery payload (rather than guessing
    at repair time) keeps synthesised hubs aligned with the real source
    schema, so downstream rendering produces correct SQL.
    """
    hints: dict[str, dict[str, Any]] = {}
    for table in tables:
        business_keys: list[str] = []
        for col in table.columns:
            if col.is_system:
                continue
            prof = col.profile
            if prof is None:
                continue
            if prof.is_likely_key or prof.cardinality_ratio >= _SYNTH_KEY_CARDINALITY:
                business_keys.append(col.name)
                if len(business_keys) >= _SYNTH_MAX_BUSINESS_KEYS:
                    break
        if not business_keys:
            # Fallback: first non-system column, then "id" as last resort.
            for col in table.columns:
                if not col.is_system:
                    business_keys = [col.name]
                    break
            if not business_keys:
                business_keys = ["id"]
        hints[table.name] = {
            "business_keys": business_keys,
            "hash_key": f"HK_{table.name.upper()}",
        }
    return hints


def _repair_plan_data(
    plan_data: dict[str, Any],
    *,
    sample_idx: int,
    synthesis_hints: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Strip extras AND repair satellite/hub references in-place.

    The LLM consistently exhibits two failure modes that abort
    otherwise-valid samples:

    1. **Stray fields** — mirrored from prompt context (e.g. hint bucket
       names emitted as satellite keys). Stripped using
       ``model_cls.model_fields`` so no field names are hardcoded —
       adding fields to a decision model is automatically picked up.
    2. **Orphan satellites** — a satellite's ``parent_hub`` does not
       match any emitted hub. Two recovery paths:

       a. The LLM named the hub slightly differently (e.g.
          ``hub_volume_metrics`` vs ``hub_volumemetrics``). When the
          orphan satellite shares its ``source_table`` with an existing
          hub we repoint the satellite to that hub's name.
       b. The LLM omitted the hub entirely. We synthesise a minimum-valid
          hub from the satellite's ``source_table`` using the
          discovery-derived ``synthesis_hints`` so the resulting hub
          carries real business keys (not guesses).

    Every repair logs at WARNING so genuine modelling drift remains
    visible. The function is intentionally generic — it does not know
    anything about Data Vault semantics beyond the decision contracts.
    """
    # ── 1) Strip unknown fields ────────────────────────────────────────────
    for key, model_cls in _DECISION_MODEL_BY_KEY.items():
        entries = plan_data.get(key)
        if not isinstance(entries, list):
            continue
        allowed = set(model_cls.model_fields.keys())
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            extras = [k for k in entry if k not in allowed]
            for extra_key in extras:
                value = entry.pop(extra_key)
                _LOG.warning(
                    "sample %d: stripped unknown field %s.%d.%s=%r before validation",
                    sample_idx,
                    key,
                    idx,
                    extra_key,
                    value,
                )

    # ── 2) Repair orphan satellites ────────────────────────────────────────
    hubs = plan_data.get("hubs")
    sats = plan_data.get("satellites")
    if not isinstance(hubs, list) or not isinstance(sats, list):
        return

    hub_names: set[str] = {
        h["name"] for h in hubs if isinstance(h, dict) and isinstance(h.get("name"), str)
    }
    hubs_by_source: dict[str, dict[str, Any]] = {
        h["source_table"]: h
        for h in hubs
        if isinstance(h, dict)
        and isinstance(h.get("source_table"), str)
        and isinstance(h.get("name"), str)
    }
    synthesis_hints = synthesis_hints or {}

    for sat in sats:
        if not isinstance(sat, dict):
            continue
        parent = sat.get("parent_hub")
        if not isinstance(parent, str) or parent in hub_names:
            continue
        source_table = sat.get("source_table")
        if not isinstance(source_table, str):
            continue
        # 2a) Repoint when a hub already exists for this source table.
        matching_hub = hubs_by_source.get(source_table)
        if matching_hub is not None:
            new_parent = matching_hub["name"]
            _LOG.warning(
                "sample %d: repointed satellite %r parent_hub %r -> %r "
                "(matched on source_table=%r)",
                sample_idx,
                sat.get("name"),
                parent,
                new_parent,
                source_table,
            )
            sat["parent_hub"] = new_parent
            continue
        # 2b) Synthesise a minimum-valid hub using discovery-derived keys.
        hint = synthesis_hints.get(source_table, {})
        business_keys = list(hint.get("business_keys") or ["id"])
        hash_key = hint.get("hash_key") or f"HK_{source_table.upper()}"
        synth_hub = {
            "name": parent,
            "source_table": source_table,
            "kind": "hub",
            "business_keys": business_keys,
            "hash_key": hash_key,
            "confidence": "low",
            "rationale": (
                f"Synthesised by repair pass: satellite {sat.get('name')!r} "
                f"referenced unknown parent_hub {parent!r} for source table "
                f"{source_table!r}; LLM omitted the hub."
            ),
        }
        hubs.append(synth_hub)
        hub_names.add(parent)
        hubs_by_source[source_table] = synth_hub
        _LOG.warning(
            "sample %d: synthesised missing hub %r (source_table=%r, "
            "business_keys=%r, hash_key=%r) for orphan satellite %r",
            sample_idx,
            parent,
            source_table,
            business_keys,
            hash_key,
            sat.get("name"),
        )


class ModellingAgentError(RuntimeError):
    """Raised when the agent cannot produce a single valid modelling plan."""


class ModellingAgent:
    """LLM-backed modelling agent.

    Parameters
    ----------
    client
        Pre-built ``AzureOpenAI`` instance. Use :func:`get_modelling_agent`
        to construct one from settings.
    deployment
        Chat deployment name (e.g. ``gpt-5``, ``gpt-4o``).
    api_version
        Azure OpenAI API version. Used only for logging/telemetry.
    samples
        Number of independent completions per ``propose`` call. Defaults to 3.
        Set to 1 to disable voting (e.g. for quick smoke tests).
    max_tokens
        Token budget per completion. gpt-5 may legitimately need more;
        empty-response retries auto-double this once.
    sample_parallelism
        How many of the ``samples`` completions to issue concurrently.
        Defaults to ``1`` (sequential) for backward-compatibility with
        direct callers and tests. The :func:`get_modelling_agent` factory
        defaults this to ``samples`` so the analyze step collapses to one
        completion's wall-clock RTT in production.
    batch_size
        When > 0 and the payload's table count exceeds this, ``propose``
        splits tables into fixed-size batches and runs each batch's
        completion concurrently. Plans are then merged by name-union.
        Use to keep latency bounded on large catalogues. ``0`` (default for
        direct construction) disables batching.
    batch_parallelism
        Maximum concurrent batches. ``0`` means "as many as batches" so the
        total wall clock collapses to one batch's RTT.
    batch_samples
        Samples drawn per batch when batched mode is active. Defaults to
        ``1`` because batching already buys parallelism across tables;
        per-batch voting compounds fan-out and triggers 429s. Set to ``3``
        if you want per-batch voting and your Azure deployment can absorb
        ``num_batches × 3`` concurrent calls.
    max_prompt_tokens
        Soft cap on per-batch prompt size (estimated tokens). When > 0,
        ``_propose_batched`` flushes a batch early if adding the next
        table would push its prompt over this cap, even when the batch
        has fewer than ``batch_size`` tables. Prevents a single wide-table
        batch from blowing the per-request TPM allowance.
    large_catalog_threshold
        When the payload's table count exceeds this, sampling drops to one
        completion (no majority vote). Applied per-batch when batching is
        active, and to the whole payload otherwise. ``0`` disables.
    """

    def __init__(
        self,
        *,
        client: AzureOpenAI,
        deployment: str,
        api_version: str = "",
        samples: int = 3,
        max_tokens: int = 4096,
        tool_specs: tuple[ToolSpec, ...] | None = None,
        max_tool_rounds: int = 6,
        sample_parallelism: int = 1,
        batch_size: int = 0,
        batch_parallelism: int = 0,
        batch_samples: int = 1,
        max_prompt_tokens: int = 0,
        large_catalog_threshold: int = 0,
        max_tokens_ceiling: int = 16384,
    ) -> None:
        if samples <= 0:
            raise ValueError("samples must be positive")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if max_tool_rounds <= 0:
            raise ValueError("max_tool_rounds must be positive")
        if sample_parallelism <= 0:
            raise ValueError("sample_parallelism must be positive")
        if batch_size < 0:
            raise ValueError("batch_size must be >= 0")
        if batch_parallelism < 0:
            raise ValueError("batch_parallelism must be >= 0")
        if batch_samples <= 0:
            raise ValueError("batch_samples must be positive")
        if max_prompt_tokens < 0:
            raise ValueError("max_prompt_tokens must be >= 0")
        if large_catalog_threshold < 0:
            raise ValueError("large_catalog_threshold must be >= 0")
        if max_tokens_ceiling <= 0:
            raise ValueError("max_tokens_ceiling must be positive")
        self._client = client
        self._deployment = deployment
        self._api_version = api_version
        self._samples = samples
        self._max_tokens = max_tokens
        self._max_tokens_ceiling = max(max_tokens, max_tokens_ceiling)
        self._is_gpt5 = deployment.startswith("gpt-5")
        self._tool_specs = tool_specs
        self._max_tool_rounds = max_tool_rounds
        # Cap parallelism at samples — extra workers would idle.
        self._sample_parallelism = min(sample_parallelism, samples)
        self._batch_size = batch_size
        self._batch_parallelism = batch_parallelism
        self._batch_samples = batch_samples
        self._max_prompt_tokens = max_prompt_tokens
        self._large_catalog_threshold = large_catalog_threshold
        _LOG.info(
            "ModellingAgent ready: deployment=%s samples=%d sample_parallelism=%d "
            "max_tokens=%d max_tokens_ceiling=%d batch_size=%d batch_parallelism=%d "
            "batch_samples=%d max_prompt_tokens=%d large_catalog_threshold=%d",
            deployment,
            samples,
            self._sample_parallelism,
            max_tokens,
            self._max_tokens_ceiling,
            batch_size,
            batch_parallelism,
            batch_samples,
            max_prompt_tokens,
            large_catalog_threshold,
        )

    @property
    def deployment(self) -> str:
        return self._deployment

    # ------------------------------------------------------------------ public

    def propose(self, payload: DiscoveryPayload) -> ModelingPlan:
        """Return a validated :class:`ModelingPlan` for ``payload``.

        Dispatches to one of two strategies, transparently to the caller:

        * **Batched** (``batch_size > 0`` and ``len(tables) > batch_size``):
          tables are split into fixed-size batches, each batch produces its
          own plan in parallel, and the plans are merged. Trades cross-batch
          link discovery for ~linear speedup on large catalogues.
        * **Single** (default for small payloads): one ``DiscoveryPayload``
          → N samples with majority vote.

        In both strategies, when ``large_catalog_threshold > 0`` and the
        relevant table count exceeds it, sampling drops to one completion
        to keep latency bounded.

        Raises
        ------
        ModellingAgentError
            If no sample yields a parseable, schema-valid plan.
        """
        n_tables = len(payload.tables)
        if self._batch_size > 0 and n_tables > self._batch_size:
            return self._propose_batched(payload)
        effective_samples = self._effective_samples(n_tables)
        return self._propose_voted(payload, samples=effective_samples)

    # ------------------------------------------------------------------ batching

    def _effective_samples(self, n_tables: int) -> int:
        """Per-call sample count after the large-catalogue threshold."""
        if self._large_catalog_threshold > 0 and n_tables > self._large_catalog_threshold:
            return 1
        return self._samples

    def _propose_batched(self, payload: DiscoveryPayload) -> ModelingPlan:
        """Split tables into batches, propose each in parallel, merge plans.

        Each batch carries the same :class:`SourceSystem` so the resulting
        plans share a ``system_id`` and can be unioned safely. The per-batch
        sample count is computed from ``batch_size`` (the per-batch table
        count cap), not the total — batches are normally small enough to
        stay below the large-catalogue threshold.
        """
        import time as _time

        tables = tuple(payload.tables)
        size = self._batch_size
        batches: list[tuple[SourceTable, ...]] = _chunk_tables(
            tables, max_tables=size, max_prompt_tokens=self._max_prompt_tokens
        )
        batch_payloads = [
            payload.model_copy(update={"tables": b}) for b in batches
        ]
        max_workers = self._batch_parallelism or len(batch_payloads)
        per_batch_samples = self._batch_samples
        batch_sizes = [len(b.tables) for b in batch_payloads]
        _LOG.info(
            "ModellingAgent.propose: batching %d tables into %d batch(es) "
            "(sizes=%s, max_tables=%d, max_prompt_tokens=%d), "
            "parallelism=%d, samples_per_batch=%d",
            len(tables),
            len(batch_payloads),
            batch_sizes,
            size,
            self._max_prompt_tokens,
            max_workers,
            per_batch_samples,
        )
        t0 = _time.perf_counter()

        def _one_batch(idx_and_payload: tuple[int, DiscoveryPayload]) -> ModelingPlan:
            idx, sub_payload = idx_and_payload
            t_batch = _time.perf_counter()
            plan = self._propose_voted(sub_payload, samples=per_batch_samples)
            _LOG.info(
                "ModellingAgent batch %d/%d ok in %.1fs (tables=%d, hubs=%d, links=%d, sats=%d)",
                idx + 1,
                len(batch_payloads),
                _time.perf_counter() - t_batch,
                len(sub_payload.tables),
                len(plan.hubs),
                len(plan.links),
                len(plan.satellites),
            )
            return plan

        if max_workers <= 1 or len(batch_payloads) == 1:
            plans = [_one_batch((i, p)) for i, p in enumerate(batch_payloads)]
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                plans = list(pool.map(_one_batch, enumerate(batch_payloads)))

        merged = _merge_plans(plans, system_id=payload.system.system_id)
        _LOG.info(
            "ModellingAgent.propose: %d batch(es) merged in %.1fs wall clock "
            "(hubs=%d, links=%d, sats=%d)",
            len(batch_payloads),
            _time.perf_counter() - t0,
            len(merged.hubs),
            len(merged.links),
            len(merged.satellites),
        )
        return merged

    # ------------------------------------------------------------------ voting

    def _propose_voted(self, payload: DiscoveryPayload, *, samples: int) -> ModelingPlan:
        """Draw ``samples`` completions for ``payload``, vote, return winner.

        Used both by the single-prompt path and as the per-batch primitive
        in :meth:`_propose_batched`.
        """
        import time as _time

        _t0 = _time.perf_counter()
        user_prompt = _build_user_prompt(payload)
        synthesis_hints = _build_synthesis_hints(payload.tables)
        parallelism = min(self._sample_parallelism, samples)
        _LOG.info(
            "ModellingAgent.propose: drawing %d sample(s) with parallelism=%d "
            "(prompt=%d chars, %d tables)",
            samples,
            parallelism,
            len(user_prompt),
            len(payload.tables),
        )
        if parallelism <= 1 or samples <= 1:
            per_sample = [
                self._draw_sample(
                    idx, user_prompt, payload.system.system_id, synthesis_hints
                )
                for idx in range(samples)
            ]
        else:
            per_sample = self._draw_samples_parallel(
                user_prompt,
                payload.system.system_id,
                samples=samples,
                max_workers=parallelism,
                synthesis_hints=synthesis_hints,
            )
        _LOG.info(
            "ModellingAgent.propose: all %d sample(s) finished in %.1fs (wall clock)",
            samples,
            _time.perf_counter() - _t0,
        )

        candidates: list[ModelingPlan] = []
        errors: list[str] = []
        for plan, error in per_sample:
            if plan is not None:
                candidates.append(plan)
            if error is not None:
                errors.append(error)

        if not candidates:
            raise ModellingAgentError(
                "ModellingAgent produced no valid plans across "
                f"{samples} samples. Details: " + "; ".join(errors)
            )
        return _vote(candidates)

    # ---------------------------------------------------------------- internals

    def _draw_samples_parallel(
        self,
        user_prompt: str,
        system_id: str,
        *,
        samples: int | None = None,
        max_workers: int | None = None,
        synthesis_hints: dict[str, dict[str, Any]] | None = None,
    ) -> list[tuple[ModelingPlan | None, str | None]]:
        """Issue ``samples`` completions concurrently, preserving order.

        Order matters: :func:`_vote` tie-breaks by ``candidates.index(p)``,
        and stable ordering keeps the chosen plan reproducible run-to-run
        for an identical set of model responses.
        """
        n = self._samples if samples is None else samples
        workers = self._sample_parallelism if max_workers is None else max_workers
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(
                pool.map(
                    lambda idx: self._draw_sample(
                        idx, user_prompt, system_id, synthesis_hints
                    ),
                    range(n),
                )
            )

    def _draw_sample(
        self,
        sample_idx: int,
        user_prompt: str,
        system_id: str,
        synthesis_hints: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[ModelingPlan | None, str | None]:
        """One completion + parse + validate. Returns ``(plan, error)``."""
        import time as _time

        _t0 = _time.perf_counter()
        raw = self._one_completion(user_prompt)
        _LOG.info(
            "ModellingAgent sample %d completed in %.1fs (%d chars)",
            sample_idx,
            _time.perf_counter() - _t0,
            len(raw or ""),
        )
        if not raw:
            return None, f"sample {sample_idx}: empty response after retry"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            # The most common cause of invalid JSON from a JSON-mode call is
            # the model hitting ``max_tokens`` mid-string. Retry once with a
            # doubled budget before giving up — this rescues batches that
            # would otherwise force the whole pipeline to fail after minutes.
            retry_budget = min(self._max_tokens * 2, self._max_tokens_ceiling)
            _LOG.warning(
                "Modelling sample %d: invalid JSON (%s); retrying with budget %d (ceiling=%d)",
                sample_idx,
                exc,
                retry_budget,
                self._max_tokens_ceiling,
            )
            retry_raw = self._call_single(
                [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                self._build_kwargs(retry_budget),
            )
            if not retry_raw:
                return None, f"sample {sample_idx}: invalid JSON ({exc}); retry empty"
            try:
                data = json.loads(retry_raw)
            except json.JSONDecodeError as exc2:
                return None, f"sample {sample_idx}: invalid JSON after retry ({exc2})"
        if not isinstance(data, dict):
            return (
                None,
                f"sample {sample_idx}: top-level JSON is {type(data).__name__}, expected object",
            )
        # Force the system_id on the way in so the model can't drift.
        data["system_id"] = system_id
        # Strip LLM-emitted extras (e.g. mirrored hint keys) so a single
        # stray field doesn't abort an otherwise-valid sample. Logs each
        # removal at WARNING so genuine drift remains visible.
        _repair_plan_data(data, sample_idx=sample_idx, synthesis_hints=synthesis_hints)
        try:
            return ModelingPlan.model_validate(data), None
        except ValidationError as exc:
            _LOG.warning("Modelling sample %d failed validation: %s", sample_idx, exc)
            first_msgs = "; ".join(
                f"{'.'.join(str(x) for x in err.get('loc', ()))}: {err.get('msg', '')}"
                for err in exc.errors()[:3]
            )
            return (
                None,
                f"sample {sample_idx}: schema invalid ({exc.error_count()} errors) [{first_msgs}]",
            )

    def _one_completion(self, user_prompt: str) -> str:
        """One chat call with model-specific kwargs and one empty-response retry."""
        kwargs = self._build_kwargs(min(self._max_tokens, self._max_tokens_ceiling))
        content = self._call(user_prompt, kwargs)
        if content or not self._is_gpt5:
            return content
        # gpt-5 occasionally returns empty content on the first attempt; retry
        # once with a doubled token budget. Retry always bypasses the tool loop
        # (which is incompatible with response_format=json_object).
        retry_budget = min(self._max_tokens * 2, self._max_tokens_ceiling)
        _LOG.warning(
            "gpt-5 returned empty content; retrying with budget %d (ceiling=%d)",
            retry_budget,
            self._max_tokens_ceiling,
        )
        return self._call_single(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            self._build_kwargs(retry_budget),
        )

    def _build_kwargs(self, token_budget: int) -> dict[str, Any]:
        if self._is_gpt5:
            return {
                "temperature": 1.0,
                "max_completion_tokens": token_budget,
                "response_format": {"type": "json_object"},
            }
        return {
            "temperature": 0.0,
            "max_tokens": token_budget,
            "response_format": {"type": "json_object"},
        }

    def _call(self, user_prompt: str, kwargs: dict[str, Any]) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        if self._tool_specs:
            try:
                return run_tool_loop(
                    client=self._client,
                    deployment=self._deployment,
                    call_kwargs=kwargs,
                    initial_messages=messages,
                    tools=self._tool_specs,
                    max_rounds=self._max_tool_rounds,
                )
            except ToolLoopError as exc:
                _LOG.warning("Tool loop failed (%s); falling back to single-shot call", exc)
        return self._call_single(messages, kwargs)

    def _call_single(self, messages: list[dict[str, Any]], kwargs: dict[str, Any]) -> str:
        # Two-stage gating: first reserve TPM (blocks until our deployment's
        # token bucket has capacity), then take an RPM permit. Order matters:
        # reserving tokens first means workers queue at the token bucket
        # rather than holding an RPM permit while waiting for TPM, which
        # would deadlock at low concurrency settings.
        estimated = _estimate_call_tokens(messages, kwargs)
        _get_llm_token_bucket().acquire(estimated)
        with _get_llm_semaphore():
            response = self._client.chat.completions.create(
                model=self._deployment,
                messages=messages,
                **kwargs,
            )
        return (response.choices[0].message.content or "").strip()


# ====================================================================== prompt


def _build_user_prompt(payload: DiscoveryPayload) -> str:
    """Render a compact JSON description of the source system.

    We include a concise JSON-schema hint inside the prompt because Azure
    response_format=json_object guarantees JSON syntax but not field shape.
    Keeping the schema hint here (rather than relying on the SDK's structured
    outputs) keeps the agent portable across SDK / API-version variations.
    """
    tables: list[SourceTable] = list(payload.tables[:_MAX_TABLES_IN_PROMPT])
    body = {
        "system": {
            "system_id": payload.system.system_id,
            "system_name": payload.system.system_name,
            "source_type": payload.system.source_type,
        },
        "tables": [_summarise_table(t) for t in tables],
        "sat_split_hint": build_sat_split_hint(tables),
    }
    schema_hint = {
        "system_id": "string",
        "hubs": [
            {
                "name": "hub_<concept>",
                "source_table": "string",
                "business_keys": ["string"],
                "hash_key": "HK_<CONCEPT>",
                "confidence": "low|medium|high",
                "rationale": "short string",
            }
        ],
        "links": [
            {
                "name": "link_<rel>",
                "source_table": "string",
                "hash_key": "HK_<REL>",
                "fk_columns": ["HK_HUB_A", "HK_HUB_B"],
                "confidence": "low|medium|high",
                "rationale": "short string",
            }
        ],
        "satellites": [
            {
                "name": "sat_<hub>[_<subgroup>]",
                "source_table": "string",
                "parent_hub": "hub_<concept>",
                "hash_key": "HK_<CONCEPT>",
                "hashdiff": "HD_<CONCEPT>[_<SUBGROUP>]",
                "payload": ["col_a", "col_b"],
                "effective_from": "optional column or null",
                "subgroup": "details|operational|measurements|null",
                "change_velocity": "static|dynamic|mixed",
                "confidence": "low|medium|high",
                "rationale": "short string",
            }
        ],
    }
    return (
        "Source system:\n"
        + json.dumps(body, indent=2, ensure_ascii=False)
        + "\n\nReturn JSON with EXACTLY these top-level keys: "
        "system_id, hubs, links, satellites.\n"
        "Use this shape for each entry (omit unknown optional fields):\n"
        + json.dumps(schema_hint, indent=2)
    )


def _estimate_table_tokens(table: SourceTable) -> int:
    """Rough token estimate for the JSON form of a single table.

    Used by :func:`_chunk_tables` to decide when a batch's prompt is large
    enough to flush early. Same 4-chars/token heuristic as the runtime
    token bucket so the two stay consistent.
    """
    try:
        return math.ceil(len(json.dumps(_summarise_table(table))) / _CHARS_PER_TOKEN)
    except Exception:
        return 0


def _chunk_tables(
    tables: Sequence[SourceTable],
    *,
    max_tables: int,
    max_prompt_tokens: int,
) -> list[tuple[SourceTable, ...]]:
    """Size-balanced batching: respect both per-batch table count and token budget.

    A batch is flushed when adding the next table would exceed *either*
    ``max_tables`` or ``max_prompt_tokens`` (when > 0). Single tables that
    exceed the token cap on their own are emitted as a one-table batch
    so we never silently drop input. Preserves input order so related
    tables that are adjacent in the catalog stay in the same batch.
    """
    out: list[tuple[SourceTable, ...]] = []
    cur: list[SourceTable] = []
    cur_tokens = 0
    for t in tables:
        t_tokens = _estimate_table_tokens(t) if max_prompt_tokens > 0 else 0
        too_many = max_tables > 0 and len(cur) >= max_tables
        too_big = (
            max_prompt_tokens > 0
            and cur
            and (cur_tokens + t_tokens) > max_prompt_tokens
        )
        if cur and (too_many or too_big):
            out.append(tuple(cur))
            cur, cur_tokens = [], 0
        cur.append(t)
        cur_tokens += t_tokens
    if cur:
        out.append(tuple(cur))
    return out


def _summarise_table(table: SourceTable) -> dict[str, Any]:
    wide = len(table.columns) > _WIDE_TABLE_COLUMN_THRESHOLD
    out: dict[str, Any] = {
        "name": table.name,
        "fully_qualified_name": table.fully_qualified_name,
        "columns": [_summarise_column(c, compact=wide) for c in table.columns],
    }
    if table.description:
        # Always keep table-level description — it's the single best hint for
        # naming hubs after concepts instead of source table names. Truncate
        # only in wide mode to bound token cost.
        if wide and len(table.description) > _WIDE_TABLE_TEXT_TRUNCATE * 2:
            out["description"] = table.description[: _WIDE_TABLE_TEXT_TRUNCATE * 2]
        else:
            out["description"] = table.description
    return out


def _summarise_column(col: SourceColumn, *, compact: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": col.name,
        "type": col.inferred_type.value,
        "nullable": col.nullable,
    }
    # Description and key signals are mandatory for plan quality — without
    # them the modeller cannot tell a surrogate GUID from a real business
    # key, and FK relationships across tables disappear. Keep them in both
    # compact and verbose modes; only truncate long descriptions in compact.
    if col.description:
        if compact and len(col.description) > _WIDE_TABLE_TEXT_TRUNCATE:
            out["description"] = col.description[:_WIDE_TABLE_TEXT_TRUNCATE]
        else:
            out["description"] = col.description
    if col.profile is not None:
        out["null_rate"] = round(col.profile.null_rate, 3)
        out["cardinality_ratio"] = round(col.profile.cardinality_ratio, 3)
        out["is_likely_key"] = col.profile.is_likely_key
        if col.profile.sample_values:
            samples = list(col.profile.sample_values[:_MAX_SAMPLE_VALUES_PER_COLUMN])
            if compact:
                samples = [
                    (s[:_WIDE_TABLE_TEXT_TRUNCATE] if isinstance(s, str) else s)
                    for s in samples
                ]
            out["samples"] = samples
    return out


# ========================================================================= vote


def _fingerprint(plan: ModelingPlan) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Order-insensitive identity of a plan for majority voting."""
    return (
        tuple(sorted(h.name for h in plan.hubs)),
        tuple(sorted(ln.name for ln in plan.links)),
        tuple(sorted(s.name for s in plan.satellites)),
    )


def _total_confidence(plan: ModelingPlan) -> int:
    return (
        sum(_CONFIDENCE_WEIGHT[h.confidence] for h in plan.hubs)
        + sum(_CONFIDENCE_WEIGHT[ln.confidence] for ln in plan.links)
        + sum(_CONFIDENCE_WEIGHT[s.confidence] for s in plan.satellites)
    )


def _vote(candidates: Sequence[ModelingPlan]) -> ModelingPlan:
    """Return the majority plan; ties broken by highest total confidence."""
    if len(candidates) == 1:
        return candidates[0]

    counts = Counter(_fingerprint(p) for p in candidates)
    top_count = max(counts.values())
    winning_fps = {fp for fp, c in counts.items() if c == top_count}
    finalists = [p for p in candidates if _fingerprint(p) in winning_fps]
    # Stable ordering: highest confidence wins; tie -> earliest sample.
    finalists.sort(key=lambda p: (-_total_confidence(p), candidates.index(p)))
    return finalists[0]


def _merge_plans(plans: Sequence[ModelingPlan], *, system_id: str) -> ModelingPlan:
    """Union per-batch plans into a single :class:`ModelingPlan`.

    Dedup strategy: keep the first decision per ``name``. Tables don't
    overlap across batches in the current batching scheme, so collisions
    are rare; when they do occur (e.g. the model reuses a generic hub
    name like ``hub_party``), preferring the earlier batch keeps the
    merge deterministic.

    Quality caveat: links between hubs in different batches cannot be
    produced — the modeller only sees one batch at a time. Callers that
    need cross-batch links should widen ``modeller_batch_size`` or run a
    follow-up reconciliation pass (not implemented in this version).
    """
    if not plans:
        raise ValueError("_merge_plans requires at least one plan")
    if len(plans) == 1:
        return plans[0]

    seen_hub: set[str] = set()
    seen_link: set[str] = set()
    seen_sat: set[str] = set()
    hubs: list[Any] = []
    links: list[Any] = []
    sats: list[Any] = []
    for p in plans:
        for h in p.hubs:
            if h.name not in seen_hub:
                seen_hub.add(h.name)
                hubs.append(h)
        for ln in p.links:
            if ln.name not in seen_link:
                seen_link.add(ln.name)
                links.append(ln)
        for s in p.satellites:
            if s.name not in seen_sat:
                seen_sat.add(s.name)
                sats.append(s)

    # Drop satellites whose parent hub didn't survive the merge — the
    # ModelingPlan validator would otherwise reject the whole plan.
    hub_names = {h.name for h in hubs}
    dropped = [s.name for s in sats if s.parent_hub not in hub_names]
    if dropped:
        _LOG.warning(
            "_merge_plans: dropping %d satellite(s) with unknown parent hub: %s",
            len(dropped),
            ", ".join(dropped[:5]) + ("…" if len(dropped) > 5 else ""),
        )
        sats = [s for s in sats if s.parent_hub in hub_names]

    return ModelingPlan(
        system_id=system_id,
        hubs=tuple(hubs),
        links=tuple(links),
        satellites=tuple(sats),
    )


# ====================================================================== factory


def get_modelling_agent(
    *,
    settings: AISettings | None = None,
    deployment: str | None = None,
    samples: int = 3,
    max_tokens: int | None = None,
    tool_specs: tuple[ToolSpec, ...] | None = None,
    max_tool_rounds: int = 6,
    sample_parallelism: int | None = None,
    batch_size: int | None = None,
    batch_parallelism: int | None = None,
    batch_samples: int | None = None,
    max_prompt_tokens: int | None = None,
    large_catalog_threshold: int | None = None,
    max_tokens_ceiling: int | None = None,
) -> ModellingAgent:
    """Build a :class:`ModellingAgent` from settings.

    ``deployment`` defaults to ``settings.primary_chat_deployment`` (gpt-5).
    Pass ``settings.chat_deployment_gpt4o`` explicitly to evaluate gpt-4o.

    ``max_tokens`` defaults to the per-deployment budget configured on
    :class:`AISettings` (see :meth:`AISettings.modeller_max_tokens_for`).
    Pass an explicit integer to override (useful for tests pinning behaviour).

    ``sample_parallelism`` defaults to
    :attr:`AISettings.modeller_sample_parallelism`; the setting's ``0``
    sentinel expands to ``samples`` so all completions run concurrently.

    ``batch_size``, ``batch_parallelism``, and ``large_catalog_threshold``
    default to the matching ``modeller_*`` settings. With defaults, any
    payload above ``modeller_batch_size`` tables is split into batches
    that run in parallel and use a single completion each, keeping
    wall-clock latency roughly constant as the catalogue grows.
    """
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import get_settings

    cfg = settings or get_settings()
    # Prefer the modeller-specific deployment (defaults to gpt-4o) so the
    # hot, fan-out-heavy modelling step does not share gpt-5's tight TPM
    # with the rest of the pipeline. An explicit ``deployment`` argument
    # (used by tests and ops scripts) always wins.
    chosen = deployment or getattr(cfg, "modeller_chat_deployment", None) or cfg.primary_chat_deployment
    budget = max_tokens if max_tokens is not None else cfg.modeller_max_tokens_for(chosen)
    if sample_parallelism is None:
        configured = cfg.modeller_sample_parallelism
        sample_parallelism = samples if configured == 0 else configured
    if batch_size is None:
        batch_size = cfg.modeller_batch_size
    if batch_parallelism is None:
        batch_parallelism = cfg.modeller_batch_parallelism
    if batch_samples is None:
        batch_samples = cfg.modeller_batch_samples
    if max_prompt_tokens is None:
        max_prompt_tokens = cfg.modeller_max_prompt_tokens
    if large_catalog_threshold is None:
        large_catalog_threshold = cfg.modeller_large_catalog_threshold
    if max_tokens_ceiling is None:
        max_tokens_ceiling = cfg.modeller_max_tokens_ceiling
    client = AzureOpenAI(
        azure_endpoint=cfg.azure_openai_endpoint,
        api_key=cfg.azure_openai_api_key.get_secret_value(),
        api_version=cfg.azure_openai_api_version,
        max_retries=cfg.llm_max_retries,
    )
    return ModellingAgent(
        client=client,
        deployment=chosen,
        api_version=cfg.azure_openai_api_version,
        samples=samples,
        max_tokens=budget,
        tool_specs=tool_specs,
        max_tool_rounds=max_tool_rounds,
        sample_parallelism=sample_parallelism,
        batch_size=batch_size,
        batch_parallelism=batch_parallelism,
        batch_samples=batch_samples,
        max_prompt_tokens=max_prompt_tokens,
        large_catalog_threshold=large_catalog_threshold,
        max_tokens_ceiling=max_tokens_ceiling,
    )
