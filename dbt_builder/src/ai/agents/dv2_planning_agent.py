"""DV2 Planning Agent — opt-in, single-call structured-plan emitter.

The agent issues one chat completion that returns a strict-validated
JSON document describing the *planning* layer of a Data Vault build:

* ``hub_decisions``      — chosen business keys + rationales
* ``link_decisions``     — unary / N-ary relationship hashing strategy
* ``satellite_splits``   — payload column → sat-name partitioning hints
* ``reference_tables``   — small lookup / dimension candidates
* ``bv_proposals``       — derived sats with reproducible derivation SQL
* ``pit_volume_estimates`` — row-count band per PIT (sm / md / lg / xl)
* ``edge_cases``         — known-ambiguous tables flagged for human eyes
* ``review_flags``       — recommended human-in-the-loop pause points

The output is *advisory*: it is consumed by the modeller / BV architect
as additional context, not as a replacement for their own validation.
Default OFF (``AISettings.planning_agent_enabled`` = False); enabling
it costs one extra chat call per pipeline run.

This module deliberately keeps its surface small — no orchestrator
wiring, no supervisor pause hooks — so it can be merged independently
of the rest of the pipeline.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.payloads import DiscoveryPayload

if TYPE_CHECKING:
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import AISettings


_LOG = logging.getLogger(__name__)


# ── pydantic v2 contract ────────────────────────────────────────────────────


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PlannedHub(_Frozen):
    table: str
    business_keys: tuple[str, ...]
    confidence: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class PlannedLink(_Frozen):
    name: str
    related_hubs: tuple[str, ...]
    confidence: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class PlannedSatelliteSplit(_Frozen):
    parent_hub: str
    sat_name: str
    columns: tuple[str, ...]
    rationale: str = ""


class PlannedReferenceTable(_Frozen):
    table: str
    rationale: str = ""


class PlannedBvProposal(_Frozen):
    name: str
    parent_hub: str
    payload: tuple[str, ...]
    derivation_sql: str
    rationale: str = ""


class PlannedPitVolume(_Frozen):
    pit_name: str
    estimated_band: Literal["sm", "md", "lg", "xl"]
    rationale: str = ""


class PlannedEdgeCase(_Frozen):
    table: str
    issue: str
    suggested_action: str = ""


class PlannedReviewFlag(_Frozen):
    target: str
    reason: str


class Dv2Plan(_Frozen):
    """Structured DV2 planning document — the agent's sole output."""

    system_id: str
    hub_decisions: tuple[PlannedHub, ...] = ()
    link_decisions: tuple[PlannedLink, ...] = ()
    satellite_splits: tuple[PlannedSatelliteSplit, ...] = ()
    reference_tables: tuple[PlannedReferenceTable, ...] = ()
    bv_proposals: tuple[PlannedBvProposal, ...] = ()
    pit_volume_estimates: tuple[PlannedPitVolume, ...] = ()
    edge_cases: tuple[PlannedEdgeCase, ...] = ()
    review_flags: tuple[PlannedReviewFlag, ...] = ()


class Dv2PlanningAgentError(RuntimeError):
    """Raised when the agent's reply cannot be parsed into a :class:`Dv2Plan`."""


# ── prompts ────────────────────────────────────────────────────────────────


_SYSTEM_PROMPT = (
    "You are a senior Data Vault 2.0 architect. Given a discovery payload "
    "describing source tables and columns, emit a STRICT JSON object that "
    "matches the schema below. Return ONLY the JSON object — no commentary, "
    "no markdown fences.\n\n"
    "Schema (all arrays may be empty; every field is required):\n"
    "{\n"
    '  "system_id": string,\n'
    '  "hub_decisions":        [{ "table": str, "business_keys": [str], '
    '"confidence": "high"|"medium"|"low", "rationale": str }],\n'
    '  "link_decisions":       [{ "name": str, "related_hubs": [str], '
    '"confidence": "high"|"medium"|"low", "rationale": str }],\n'
    '  "satellite_splits":     [{ "parent_hub": str, "sat_name": str, '
    '"columns": [str], "rationale": str }],\n'
    '  "reference_tables":     [{ "table": str, "rationale": str }],\n'
    '  "bv_proposals":         [{ "name": str, "parent_hub": str, '
    '"payload": [str], "derivation_sql": str, "rationale": str }],\n'
    '  "pit_volume_estimates": [{ "pit_name": str, '
    '"estimated_band": "sm"|"md"|"lg"|"xl", "rationale": str }],\n'
    '  "edge_cases":           [{ "table": str, "issue": str, '
    '"suggested_action": str }],\n'
    '  "review_flags":         [{ "target": str, "reason": str }]\n'
    "}\n\n"
    "Rules:\n"
    "1. Prefer stable surrogate IDs (mrid, sys_id, uuid) over mutable codes.\n"
    "2. Split satellites by rate-of-change OR semantic domain — never both.\n"
    "3. Only propose BVs whose derivation_sql references columns visible in "
    "the payload of the named parent hub.\n"
    "4. Flag tables you cannot confidently classify under review_flags "
    "rather than guessing.\n"
)


# ── agent ──────────────────────────────────────────────────────────────────


class Dv2PlanningAgent:
    """Single-call structured-plan emitter.

    Parameters
    ----------
    client
        Authenticated Azure OpenAI client.
    deployment
        Chat deployment name; gpt-5 family uses ``max_completion_tokens``
        + ``temperature=1``, all others use ``max_tokens`` + ``temperature=0``.
    settings
        :class:`AISettings`; only ``llm_seed`` is consulted.
    max_tokens
        Output budget for the structured reply. 4000 is enough for a
        ~50-table catalogue; raise for very wide schemas.
    """

    def __init__(
        self,
        *,
        client: AzureOpenAI,
        deployment: str,
        settings: AISettings,
        max_tokens: int = 4000,
    ) -> None:
        self._client = client
        self._deployment = deployment
        self._settings = settings
        self._max_tokens = max_tokens
        self._is_gpt5 = deployment.startswith("gpt-5")

    def plan(self, payload: DiscoveryPayload) -> Dv2Plan:
        """Return a validated :class:`Dv2Plan` for ``payload``.

        Raises
        ------
        Dv2PlanningAgentError
            If the reply is empty, not valid JSON, or fails schema validation.
        """
        user_prompt = self._build_user_prompt(payload)
        raw = self._call(user_prompt)
        if not raw:
            raise Dv2PlanningAgentError("Dv2PlanningAgent returned an empty completion")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise Dv2PlanningAgentError(f"Dv2PlanningAgent reply is not JSON: {exc}") from exc
        data["system_id"] = payload.system.system_id  # authoritative
        try:
            return Dv2Plan(**data)
        except Exception as exc:  # noqa: BLE001 — surface pydantic errors verbatim
            raise Dv2PlanningAgentError(f"Dv2PlanningAgent reply failed schema validation: {exc}") from exc

    # ── internals ─────────────────────────────────────────────────────────

    def _build_user_prompt(self, payload: DiscoveryPayload) -> str:
        ctx = {
            "system": {
                "system_id": payload.system.system_id,
                "system_name": payload.system.system_name,
                "source_type": payload.system.source_type,
            },
            "tables": [
                {
                    "name": t.name,
                    "columns": [
                        {
                            "name": c.name,
                            "dtype": c.raw_dtype,
                            "nullable": c.nullable,
                        }
                        for c in t.columns
                    ],
                }
                for t in payload.tables
            ],
        }
        return json.dumps(ctx, indent=2, sort_keys=True, default=str)

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


# ── factory ────────────────────────────────────────────────────────────────


def get_dv2_planning_agent(
    *,
    settings: AISettings | None = None,
    deployment: str | None = None,
    max_tokens: int = 4000,
) -> Dv2PlanningAgent:
    """Build a :class:`Dv2PlanningAgent` from :class:`AISettings`.

    Returns the agent regardless of the ``planning_agent_enabled`` flag —
    callers are responsible for honouring opt-in. (Keeping the gate at
    the call site means tests can instantiate the agent freely.)
    """
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import get_settings

    cfg = settings or get_settings()
    chosen = (
        deployment
        or getattr(cfg, "modeller_chat_deployment", None)
        or cfg.primary_chat_deployment
    )
    client = AzureOpenAI(
        azure_endpoint=cfg.azure_openai_endpoint,
        api_key=cfg.azure_openai_api_key.get_secret_value(),
        api_version=cfg.azure_openai_api_version,
        max_retries=cfg.llm_max_retries,
    )
    return Dv2PlanningAgent(
        client=client,
        deployment=chosen,
        settings=cfg,
        max_tokens=max_tokens,
    )
