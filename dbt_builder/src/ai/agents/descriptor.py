"""Description-enrichment agent for the rendered v3 metadata document.

The deterministic emitter (:mod:`metadata_v3_emitter`) fills every
required structural field but leaves ``description`` values as generic
f-strings like ``"PIT snapshot for the hub_terminal hub."``. This agent
performs a **single** LLM call per pipeline run to rewrite *only* the
``description`` (and ``rationale``) fields with system-aware,
business-meaningful prose.

Hard constraints (enforced by the structural diff validator below):

* The agent MAY change values where the *key* is ``description``,
  ``rationale``, or ``notes``.
* The agent MUST NOT add or remove keys anywhere in the document.
* The agent MUST NOT change values of any other key (names, payload
  lists, configs, …). Any such change is grounds for rejecting the
  enrichment and falling back to the original document.

If the LLM call fails or returns a document that does not pass the
diff, we return the original deterministic document unchanged. The
pipeline therefore degrades gracefully to "looks like v3, generic
descriptions" rather than aborting — descriptions are quality-of-life
not safety-critical.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import TYPE_CHECKING, Any

from dbt_builder.src.ai.contracts.bv import BvProposal
from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.contracts.payloads import SourceSystem

if TYPE_CHECKING:
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import AISettings

_LOG = logging.getLogger(__name__)

# Keys whose values the LLM is allowed to rewrite. Everything else is
# protected by the structural diff.
_MUTABLE_KEYS: frozenset[str] = frozenset({"description", "rationale", "notes"})

_SYSTEM_PROMPT = (
    "You are a senior Data Vault 2.0 metadata documentation specialist. "
    "You receive a YAML-as-JSON metadata document for a Data Vault 2.0 "
    "model and a small context block describing the source system and "
    "its hubs. Your ONLY task is to rewrite the 'description' (and, "
    "where present, 'rationale' or 'notes') fields with concise, "
    "business-meaningful prose grounded in the source-system context. "
    "Constraints — VIOLATING ANY OF THESE WILL CAUSE YOUR OUTPUT TO BE "
    "DISCARDED:\n"
    "1. Return the COMPLETE document with EVERY key preserved exactly.\n"
    "2. DO NOT add, remove, rename, or reorder any keys.\n"
    "3. DO NOT change any value other than 'description', 'rationale', "
    "or 'notes'.\n"
    "4. Each new description must be one sentence, <= 200 characters, "
    "ASCII only, no markdown.\n"
    "5. Reference business concepts (asset class, jurisdiction, "
    "lifecycle stage, …) where the source system context makes them "
    "evident. Do NOT invent regulatory frameworks or KPIs.\n"
    "Respond with the rewritten JSON document only — no prose."
)


class Descriptor:
    """Single-call description enricher for the v3 metadata document.

    Parameters
    ----------
    client
        Azure OpenAI client.
    deployment
        Chat deployment name. By default this reuses the modeller
        deployment (per user decision) so the document benefits from
        the same model quality without an extra deployment slot.
    settings
        :class:`AISettings`; used for the gpt-5 family flag and max
        token budget.
    max_tokens
        Per-call output budget. Defaults to 8000 — large because the
        agent rewrites the entire document, not just a delta.
    """

    def __init__(
        self,
        *,
        client: AzureOpenAI,
        deployment: str,
        settings: AISettings,
        max_tokens: int = 8000,
    ) -> None:
        self._client = client
        self._deployment = deployment
        self._settings = settings
        self._max_tokens = max_tokens
        self._is_gpt5 = deployment.startswith("gpt-5")

    def enrich(
        self,
        document: dict[str, Any],
        *,
        plan: ModelingPlan,
        system: SourceSystem,
        bv: BvProposal | None,
    ) -> dict[str, Any]:
        """Return ``document`` with descriptions rewritten by the LLM.

        Falls back to ``document`` unchanged on any error (call failure,
        invalid JSON, structural diff rejection). The fallback is
        intentional — generic descriptions are better than a broken
        pipeline.
        """
        _ = (plan, bv)  # reserved for future context injection
        try:
            prompt = self._build_user_prompt(document, system)
            raw = self._call(prompt)
        except Exception as exc:  # noqa: BLE001 - LLM site
            _LOG.warning(
                "Descriptor LLM call failed (%s); keeping deterministic "
                "descriptions.",
                exc,
            )
            return document
        try:
            enriched = json.loads(raw)
        except json.JSONDecodeError as exc:
            _LOG.warning(
                "Descriptor LLM returned invalid JSON (%s); keeping "
                "deterministic descriptions.",
                exc,
            )
            return document
        if not isinstance(enriched, dict):
            _LOG.warning(
                "Descriptor LLM returned %s; expected object.",
                type(enriched).__name__,
            )
            return document
        if not _structurally_equal(document, enriched, mutable_keys=_MUTABLE_KEYS):
            _LOG.warning(
                "Descriptor LLM altered protected fields; rejecting "
                "enrichment and keeping deterministic descriptions."
            )
            return document
        return enriched

    # ── internals ─────────────────────────────────────────────────────────

    def _build_user_prompt(
        self,
        document: dict[str, Any],
        system: SourceSystem,
    ) -> str:
        context = {
            "system": {
                "system_id": system.system_id,
                "system_name": system.system_name,
                "source_type": system.source_type,
                "description": getattr(system, "description", None),
            },
            "document": document,
        }
        return json.dumps(context, indent=2, sort_keys=False, default=str)

    def _build_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any]
        if self._is_gpt5:
            kwargs = {
                "temperature": 1.0,
                "max_completion_tokens": self._max_tokens,
                "response_format": {"type": "json_object"},
            }
        else:
            kwargs = {
                "temperature": 0.0,
                "max_tokens": self._max_tokens,
                "response_format": {"type": "json_object"},
            }
        seed = self._settings.llm_seed
        if seed >= 0:
            kwargs["seed"] = seed
        return kwargs

    def _call(self, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            **self._build_kwargs(),
        )
        return (response.choices[0].message.content or "").strip()


# ── Structural diff ─────────────────────────────────────────────────────────


def _structurally_equal(
    original: Any,
    candidate: Any,
    *,
    mutable_keys: frozenset[str],
) -> bool:
    """Return True iff ``candidate`` differs from ``original`` only at keys in ``mutable_keys``.

    Recurses through dicts and lists. Lists must be the same length;
    primitives must compare equal unless they sit under a mutable key.
    Used by :class:`Descriptor` to enforce the no-structural-change
    contract on the LLM's output.
    """
    return _diff_walk(original, candidate, mutable_keys=mutable_keys, parent_key=None)


def _diff_walk(
    original: Any,
    candidate: Any,
    *,
    mutable_keys: frozenset[str],
    parent_key: str | None,
) -> bool:
    if isinstance(original, dict):
        if not isinstance(candidate, dict):
            return False
        if set(original.keys()) != set(candidate.keys()):
            return False
        for key, orig_val in original.items():
            cand_val = candidate[key]
            if not _diff_walk(
                orig_val,
                cand_val,
                mutable_keys=mutable_keys,
                parent_key=key,
            ):
                return False
        return True
    if isinstance(original, list):
        if not isinstance(candidate, list):
            return False
        if len(original) != len(candidate):
            return False
        for orig_item, cand_item in zip(original, candidate):
            if not _diff_walk(
                orig_item,
                cand_item,
                mutable_keys=mutable_keys,
                parent_key=parent_key,
            ):
                return False
        return True
    # Primitive: allow change iff sitting directly under a mutable key.
    if parent_key in mutable_keys:
        return True
    return original == candidate


# Re-export copy so the orchestrator can deep-copy documents before
# passing them in, signalling we don't mutate inputs.
deepcopy = copy.deepcopy
