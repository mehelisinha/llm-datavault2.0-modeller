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
from collections import Counter
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from dbt_builder.src.ai.agents.tool_loop import (
    ToolLoopError,
    ToolSpec,
    run_tool_loop,
)
from dbt_builder.src.ai.contracts.decisions import (
    DecisionConfidence,
    ModelingPlan,
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
    "You are a senior Data Vault 2.0 modelling expert. "
    "You receive a JSON description of a source system (tables and columns) "
    "and propose a raw-vault model: hubs (business-key entities), links "
    "(relationships between hubs), and satellites (descriptive payloads). "
    "Follow Dan Linstedt's classical DV2 conventions: one hub per business "
    "concept, links carry no descriptive payload, and each satellite hangs "
    "off exactly one hub. Use snake_case names with a 'hub_', 'link_', or "
    "'sat_' prefix. Hash-key columns must be UPPER_SNAKE and start with 'HK_'. "
    "Return STRICT JSON matching the provided schema. Do not include any "
    "prose outside the JSON object."
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
    ) -> None:
        if samples <= 0:
            raise ValueError("samples must be positive")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if max_tool_rounds <= 0:
            raise ValueError("max_tool_rounds must be positive")
        self._client = client
        self._deployment = deployment
        self._api_version = api_version
        self._samples = samples
        self._max_tokens = max_tokens
        self._is_gpt5 = deployment.startswith("gpt-5")
        self._tool_specs = tool_specs
        self._max_tool_rounds = max_tool_rounds

    @property
    def deployment(self) -> str:
        return self._deployment

    # ------------------------------------------------------------------ public

    def propose(self, payload: DiscoveryPayload) -> ModelingPlan:
        """Return a validated :class:`ModelingPlan` for ``payload``.

        Raises
        ------
        ModellingAgentError
            If no sample yields a parseable, schema-valid plan.
        """
        user_prompt = _build_user_prompt(payload)
        candidates: list[ModelingPlan] = []
        errors: list[str] = []

        for sample_idx in range(self._samples):
            raw = self._one_completion(user_prompt)
            if not raw:
                errors.append(f"sample {sample_idx}: empty response after retry")
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"sample {sample_idx}: invalid JSON ({exc})")
                continue
            if not isinstance(data, dict):
                errors.append(
                    f"sample {sample_idx}: top-level JSON is {type(data).__name__}, expected object"
                )
                continue
            # Force the system_id on the way in so the model can't drift.
            data["system_id"] = payload.system.system_id
            try:
                candidates.append(ModelingPlan.model_validate(data))
            except ValidationError as exc:
                errors.append(f"sample {sample_idx}: schema invalid ({exc.error_count()} errors)")
                _LOG.debug("Modelling sample %d failed validation: %s", sample_idx, exc)

        if not candidates:
            raise ModellingAgentError(
                "ModellingAgent produced no valid plans across "
                f"{self._samples} samples. Details: " + "; ".join(errors)
            )
        return _vote(candidates)

    # ---------------------------------------------------------------- internals

    def _one_completion(self, user_prompt: str) -> str:
        """One chat call with model-specific kwargs and one empty-response retry."""
        kwargs = self._build_kwargs(self._max_tokens)
        content = self._call(user_prompt, kwargs)
        if content or not self._is_gpt5:
            return content
        # gpt-5 occasionally returns empty content on the first attempt; retry
        # once with a doubled token budget. Retry always bypasses the tool loop
        # (which is incompatible with response_format=json_object).
        _LOG.warning("gpt-5 returned empty content; retrying with doubled budget")
        return self._call_single(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            self._build_kwargs(self._max_tokens * 2),
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
                "name": "sat_<hub>_<topic>",
                "source_table": "string",
                "parent_hub": "hub_<concept>",
                "hash_key": "HK_<CONCEPT>",
                "hashdiff": "HD_<CONCEPT>_<TOPIC>",
                "payload": ["col_a", "col_b"],
                "effective_from": "optional column or null",
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


def _summarise_table(table: SourceTable) -> dict[str, Any]:
    return {
        "name": table.name,
        "fully_qualified_name": table.fully_qualified_name,
        "description": table.description,
        "columns": [_summarise_column(c) for c in table.columns],
    }


def _summarise_column(col: SourceColumn) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": col.name,
        "type": col.inferred_type.value,
        "nullable": col.nullable,
    }
    if col.description:
        out["description"] = col.description
    if col.profile is not None:
        out["null_rate"] = round(col.profile.null_rate, 3)
        out["cardinality_ratio"] = round(col.profile.cardinality_ratio, 3)
        out["is_likely_key"] = col.profile.is_likely_key
        if col.profile.sample_values:
            out["samples"] = list(col.profile.sample_values[:_MAX_SAMPLE_VALUES_PER_COLUMN])
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


# ====================================================================== factory


def get_modelling_agent(
    *,
    settings: AISettings | None = None,
    deployment: str | None = None,
    samples: int = 3,
    max_tokens: int | None = None,
    tool_specs: tuple[ToolSpec, ...] | None = None,
    max_tool_rounds: int = 6,
) -> ModellingAgent:
    """Build a :class:`ModellingAgent` from settings.

    ``deployment`` defaults to ``settings.primary_chat_deployment`` (gpt-5).
    Pass ``settings.chat_deployment_gpt4o`` explicitly to evaluate gpt-4o.

    ``max_tokens`` defaults to the per-deployment budget configured on
    :class:`AISettings` (see :meth:`AISettings.modeller_max_tokens_for`).
    Pass an explicit integer to override (useful for tests pinning behaviour).
    """
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import get_settings

    cfg = settings or get_settings()
    chosen = deployment or cfg.primary_chat_deployment
    budget = max_tokens if max_tokens is not None else cfg.modeller_max_tokens_for(chosen)
    client = AzureOpenAI(
        azure_endpoint=cfg.azure_openai_endpoint,
        api_key=cfg.azure_openai_api_key.get_secret_value(),
        api_version=cfg.azure_openai_api_version,
    )
    return ModellingAgent(
        client=client,
        deployment=chosen,
        api_version=cfg.azure_openai_api_version,
        samples=samples,
        max_tokens=budget,
        tool_specs=tool_specs,
        max_tool_rounds=max_tool_rounds,
    )
