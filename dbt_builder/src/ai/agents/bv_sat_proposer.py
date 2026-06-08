"""LLM-backed Business-Vault satellite proposer (pattern-gated).

Workflow
--------
1. :mod:`.bv_sat_patterns` scans the accepted :class:`ModelingPlan` and
   returns zero or more :class:`BvSatCandidate` objects. Each candidate
   names a pattern (voltage_tier, manufacturer_normalised, ...) and a
   first-pass derivation SQL skeleton.
2. If the catalogue produced **zero** candidates this proposer returns
   ``()`` immediately. No LLM call is made — saving cost and removing
   any path for the model to hallucinate satellites for systems that
   have no matching patterns. Set ``DWA_AI_BV_SATS_ENABLED=0`` to skip
   the entire step from the orchestrator.
3. For each candidate we ask the LLM to **confirm or reject** the
   proposal and, if confirmed, refine the column list and the
   derivation SQL. The LLM is explicitly forbidden from inventing new
   BV satellites beyond what the patterns surfaced — its job is
   pruning + refinement, not invention.
4. Every confirmed proposal is structurally validated: every column
   name referenced in ``derivation_sql`` must appear in the parent
   hub's raw-vault payload. Violations cause the candidate to be
   dropped (warned, not raised — one bad LLM refinement should not
   abort the whole pipeline).

Why this shape?
---------------
The user explicitly asked: *"I dont want the LLM to hallucinate"*.
Patterns are the floor (deterministic, auditable); the LLM is allowed
to add judgement on top (which tiering bands, which column variant) but
never to manufacture satellites that no pattern justified.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from dbt_builder.src.ai.agents.bv_sat_patterns import (
    BvSatCandidate,
    detect_bv_candidates,
)
from dbt_builder.src.ai.contracts.bv import (
    BvSatClassification,
    BvSatellite,
    BvSatPayloadItem,
)
from dbt_builder.src.ai.contracts.decisions import HubDecision, ModelingPlan

if TYPE_CHECKING:
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import AISettings

_LOG = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a senior Data Vault 2.0 business-vault designer. "
    "You receive a list of CANDIDATE business-vault satellite proposals "
    "that a deterministic pattern detector found in the raw vault. Your "
    "task is to CONFIRM, REFINE, or REJECT each candidate. You MAY NOT "
    "invent additional satellites beyond the candidates supplied — "
    "respond only about what is in the input. "
    "For each candidate, return a JSON object with: \n"
    "- pattern_key: copy verbatim from input\n"
    "- decision: one of 'accept', 'reject'\n"
    "- name: kept or refined satellite name (snake_case, must start "
    "'bv_sat_')\n"
    "- classification: one of 'normalisation', 'classification', "
    "'enrichment'\n"
    "- output_columns: list of derived column names (snake_case)\n"
    "- derivation_sql: refined SQL. MUST only reference columns from "
    "the supplied 'available_columns' list — referencing any other "
    "column is grounds for rejection downstream.\n"
    "- rationale: one-sentence justification\n\n"
    "Return STRICT JSON of shape {\"decisions\": [<one object per "
    "candidate>]}. No prose outside the JSON object."
)


# ── LLM response schema ─────────────────────────────────────────────────────


class _LlmDecision(BaseModel):
    """Per-candidate LLM verdict; validated structurally before use."""

    model_config = ConfigDict(extra="forbid")

    pattern_key: str
    decision: str
    name: str | None = None
    classification: str | None = None
    output_columns: tuple[str, ...] = ()
    derivation_sql: str | None = None
    rationale: str | None = None


class _LlmResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decisions: tuple[_LlmDecision, ...] = Field(default=())


# ── Derivation-SQL column-ref guardrail ─────────────────────────────────────

# Strip SQL keywords and function names that look like identifiers so the
# column-membership check doesn't false-positive on tokens like 'when',
# 'case', 'cast', 'date', etc. Kept conservative — when in doubt we'd
# rather let through a false negative (extra warning) than wrongly drop
# a valid proposal.
_SQL_KEYWORDS: frozenset[str] = frozenset(
    {
        "select", "from", "where", "and", "or", "not", "in", "is",
        "null", "case", "when", "then", "else", "end", "as", "cast",
        "current_date", "current_timestamp", "datediff", "date", "true",
        "false", "lower", "upper", "trim", "coalesce", "nullif", "int",
        "integer", "string", "varchar", "boolean", "float", "decimal",
        "between", "like", "exists", "year", "month", "day", "substr",
        "substring", "concat", "length",
    }
)

_IDENT_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")

# Strip single-quoted SQL string literals before identifier extraction.
# Without this, tokens *inside* quotes (e.g. ``'EHV'`` in a CASE
# expression) get picked up by ``_IDENT_RE`` and look like column refs.
# That false positive caused the proposer to reject its own deterministic
# starter SQL whenever the LLM accepted without rewriting the derivation.
_STRING_LITERAL_RE = re.compile(r"'(?:''|[^'])*'")


def _extract_referenced_columns(sql: str) -> set[str]:
    """Return identifier tokens in ``sql`` that look like column refs.

    Strips quoted string literals first (so tokens inside ``'…'`` are
    ignored), then SQL keywords / common function names. Numeric and
    string literals are excluded by the regex anchor.
    """
    cleaned = _STRING_LITERAL_RE.sub("", sql)
    found = {m.group(1).lower() for m in _IDENT_RE.finditer(cleaned)}
    return found - _SQL_KEYWORDS


# ── Public proposer ─────────────────────────────────────────────────────────


class LlmBvSatProposer:
    """Pattern-gated LLM proposer matching :data:`ProposeBvSatsFn`.

    Construct once per pipeline run and pass ``.propose`` to
    :class:`~dbt_builder.src.ai.agents.bv_architect.BvArchitect`.

    Parameters
    ----------
    client
        Azure OpenAI client (already authenticated).
    deployment
        Chat deployment name. Reuses the modeller deployment by default
        (per user decision) — separate value supported via ``settings``.
    settings
        :class:`AISettings`. Reads ``llm_max_tokens`` and the gpt-5
        family flag to pick the right kwargs shape (mirrors the
        modeller's logic).
    """

    def __init__(
        self,
        *,
        client: AzureOpenAI,
        deployment: str,
        settings: AISettings,
        max_tokens: int = 2000,
    ) -> None:
        self._client = client
        self._deployment = deployment
        self._settings = settings
        self._max_tokens = max_tokens
        self._is_gpt5 = deployment.startswith("gpt-5")

    # Match ProposeBvSatsFn signature exactly.
    def propose(
        self,
        plan: ModelingPlan,
        hubs: Sequence[HubDecision],
    ) -> tuple[BvSatellite, ...]:
        """Return BV satellites confirmed by the LLM, or ``()`` when none.

        ``hubs`` is passed by the architect for symmetry with future
        extensions; we currently derive hub context from ``plan`` to
        avoid two sources of truth.
        """
        _ = hubs  # plan.hubs is the authoritative source.
        candidates = detect_bv_candidates(plan)
        if not candidates:
            _LOG.info("No BV-sat patterns matched; skipping LLM proposer.")
            return ()

        prompt = self._build_user_prompt(plan, candidates)
        try:
            raw = self._call(prompt)
        except Exception as exc:  # noqa: BLE001 - LLM call site
            _LOG.warning(
                "BV-sat LLM call failed (%s); falling back to deterministic "
                "candidates without refinement.",
                exc,
            )
            return tuple(self._candidate_to_satellite(c) for c in candidates)

        try:
            data = json.loads(raw)
            llm_resp = _LlmResponse.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            _LOG.warning(
                "BV-sat LLM returned unparseable JSON (%s); falling back "
                "to deterministic candidates.",
                exc,
            )
            return tuple(self._candidate_to_satellite(c) for c in candidates)

        decisions_by_key = {d.pattern_key: d for d in llm_resp.decisions}
        confirmed: list[BvSatellite] = []
        for cand in candidates:
            verdict = decisions_by_key.get(cand.pattern_key)
            if verdict is None:
                _LOG.info(
                    "BV-sat LLM did not return a decision for '%s'; "
                    "keeping deterministic candidate.",
                    cand.pattern_key,
                )
                confirmed.append(self._candidate_to_satellite(cand))
                continue
            if verdict.decision.lower() != "accept":
                _LOG.info(
                    "BV-sat LLM rejected pattern '%s' for hub '%s': %s",
                    cand.pattern_key,
                    cand.parent_hub,
                    verdict.rationale or "(no rationale)",
                )
                continue
            sat = self._refine(cand, verdict, plan)
            if sat is not None:
                confirmed.append(sat)
        return tuple(confirmed)

    # ── internals ─────────────────────────────────────────────────────────

    def _candidate_to_satellite(self, cand: BvSatCandidate) -> BvSatellite:
        """Lift a deterministic candidate into a final BvSatellite.

        Used as the fallback path when the LLM is unavailable or its
        response is unparseable. Keeps the pipeline deterministic and
        usable in offline / unit-test contexts.
        """
        return BvSatellite(
            name=cand.name,
            parent_hub=cand.parent_hub,
            source_models=cand.source_models,
            payload=tuple(
                BvSatPayloadItem(name=c, derivation_sql=cand.derivation_sql)
                for c in cand.output_columns
            ),
            classification=cand.classification,
            rationale=cand.rationale,
        )

    def _refine(
        self,
        cand: BvSatCandidate,
        verdict: _LlmDecision,
        plan: ModelingPlan,
    ) -> BvSatellite | None:
        """Apply the LLM verdict, validating referenced columns."""
        available = {
            col.lower()
            for sat in plan.satellites
            if sat.parent_hub == cand.parent_hub
            for col in sat.payload
        }
        derivation_sql = verdict.derivation_sql or cand.derivation_sql
        referenced = _extract_referenced_columns(derivation_sql)
        unknown = referenced - available - {cand.matched_column.lower()}
        # Also tolerate column refs we deliberately produced as output of
        # the BV sat (rare — usually the SQL only references inputs).
        unknown -= {c.lower() for c in (verdict.output_columns or cand.output_columns)}
        if unknown:
            _LOG.warning(
                "BV-sat '%s' refined SQL references unknown columns %s; "
                "dropping this proposal to avoid hallucination.",
                cand.name,
                sorted(unknown),
            )
            return None

        try:
            classification = (
                BvSatClassification(verdict.classification.lower())
                if verdict.classification
                else cand.classification
            )
        except ValueError:
            classification = cand.classification

        output_cols = verdict.output_columns or cand.output_columns
        name = verdict.name or cand.name
        if not name.startswith("bv_sat_"):
            name = cand.name  # reject any rename that breaks convention

        try:
            return BvSatellite(
                name=name,
                parent_hub=cand.parent_hub,
                source_models=cand.source_models,
                payload=tuple(
                    BvSatPayloadItem(name=c, derivation_sql=derivation_sql)
                    for c in output_cols
                ),
                classification=classification,
                rationale=verdict.rationale or cand.rationale,
            )
        except ValidationError as exc:
            _LOG.warning(
                "BV-sat '%s' failed contract validation (%s); dropping.",
                name,
                exc,
            )
            return None

    def _build_user_prompt(
        self,
        plan: ModelingPlan,
        candidates: Sequence[BvSatCandidate],
    ) -> str:
        # For each candidate include the parent hub's available payload
        # columns so the LLM cannot reference columns that don't exist.
        cols_per_hub: dict[str, list[str]] = {}
        for sat in plan.satellites:
            cols_per_hub.setdefault(sat.parent_hub, []).extend(sat.payload)

        body = {
            "system_id": plan.system_id,
            "candidates": [
                {
                    "pattern_key": c.pattern_key,
                    "parent_hub": c.parent_hub,
                    "source_table": c.source_table,
                    "candidate_name": c.name,
                    "classification": c.classification.value,
                    "matched_column": c.matched_column,
                    "available_columns": sorted(set(cols_per_hub.get(c.parent_hub, []))),
                    "output_columns": list(c.output_columns),
                    "starter_derivation_sql": c.derivation_sql,
                    "starter_rationale": c.rationale,
                }
                for c in candidates
            ],
        }
        return json.dumps(body, indent=2, sort_keys=True)

    def _build_kwargs(self) -> dict[str, Any]:
        # Mirror the modeller's kwarg shape so the same deployment quirks
        # (gpt-5 temp=1.0 + max_completion_tokens) are honoured.
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
