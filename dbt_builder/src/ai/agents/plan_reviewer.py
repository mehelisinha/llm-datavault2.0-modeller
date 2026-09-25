"""LLM plan reviewer — the second model in a two-model generate → review flow.

A fast generator (the :class:`ModellingAgent`) drafts a :class:`ModelingPlan`.
This reviewer hands that draft, plus the source tables/columns, to a *stronger*
model (one call per run) and asks it to critique and patch the plan — fix weak
business keys, add missed links, split satellites by rate of change. The
corrected plan is then rendered by the deterministic emitter, so reproducibility
is preserved.

**Fail-safe by construction.** Any problem — review disabled, no deployment
configured, empty/invalid/truncated reply, schema-invalid result, or a result
that catastrophically drops the modelling — falls back to the ORIGINAL plan.
Review can only improve the plan or no-op; it can never break the pipeline.

The reviewer runs at the *plan* level (structured JSON), never on the rendered
YAML, so the emitter stays deterministic.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from dbt_builder.src.ai.agents.modeller import _build_user_prompt, _coerce_plan_dict
from dbt_builder.src.ai.contracts.decisions import LinkDecision, ModelingPlan
from dbt_builder.src.ai.contracts.payloads import DiscoveryPayload

if TYPE_CHECKING:
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import AISettings

_LOG = logging.getLogger(__name__)

# Rule file (overridable via AISettings.ai_prompts_dir); the strict-JSON output
# contract is appended in code so it can never be edited out of the rule file.
_REVIEW_RULES_NAME = "plan_review_rules"

_OUTPUT_CONTRACT = (
    "Return STRICT JSON with EXACTLY these top-level keys: system_id, hubs, "
    "links, satellites — the FULL corrected plan in the same schema as the "
    "draft. No prose, no markdown, no commentary outside the JSON object."
)

# Minimal fallback rules if the rule file is missing/unreadable.
_BUILTIN_REVIEW_RULES = (
    "You are a senior Data Vault 2.0 reviewer. You receive the source tables "
    "and a DRAFT modelling plan. Critique and correct the draft, then return "
    "the FULL corrected plan. Fix weak business keys, add missed links, and "
    "split satellites by rate of change. Never invent tables or columns. Keep "
    "correct entities and their names unchanged."
)


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    """Assemble the reviewer system prompt: file rules + code output contract."""
    from dbt_builder.src.ai.prompts import load_rules

    rules = load_rules(_REVIEW_RULES_NAME) or _BUILTIN_REVIEW_RULES
    return f"{rules}\n\n{_OUTPUT_CONTRACT}"


# Collapse guard. A review may legitimately grow the plan or trim a stray
# entity, but it must not merge away most of a class. We reject (fall back to
# the original) when the reviewer keeps fewer than ``_SHRINK_KEEP_FRACTION`` of
# any class, ignoring drops of at most ``_SHRINK_ABS_FLOOR`` so a single
# justified removal on a small plan still passes.
_SHRINK_KEEP_FRACTION = 0.7
_SHRINK_ABS_FLOOR = 1


def _class_collapsed(original: int, reviewed: int) -> bool:
    """True when ``reviewed`` is a catastrophic shrink of ``original``."""
    if reviewed >= original:
        return False  # grew or unchanged
    if reviewed == 0:
        return original > 0  # emptied a non-empty class — always a defect
    if original - reviewed <= _SHRINK_ABS_FLOOR:
        return False  # lost at most one entity — a normal refine, not a collapse
    return reviewed < original * _SHRINK_KEEP_FRACTION


def _within_shrink_tolerance(plan: ModelingPlan, reviewed: ModelingPlan) -> bool:
    """False when the reviewer collapsed hubs, links, or satellites too far."""
    return not (
        _class_collapsed(len(plan.hubs), len(reviewed.hubs))
        or _class_collapsed(len(plan.links), len(reviewed.links))
        or _class_collapsed(len(plan.satellites), len(reviewed.satellites))
    )


class PlanReviewer:
    """Single-call plan critic backed by a (stronger) chat deployment.

    Parameters
    ----------
    client
        Authenticated Azure OpenAI client.
    deployment
        Reviewer deployment name. gpt-5-family names use ``temperature=1`` +
        ``max_completion_tokens``; others use ``temperature=0`` + ``max_tokens``.
    settings
        :class:`AISettings`; reads ``llm_seed`` and the reviewer token budget.
    max_tokens
        Output budget for the corrected plan.
    """

    def __init__(
        self,
        *,
        client: AzureOpenAI,
        deployment: str,
        settings: AISettings,
        max_tokens: int = 32768,
        technical_payload_columns: frozenset[str] = frozenset(),
        preserve_business_keys: bool = True,
        link_parsimony: bool = True,
    ) -> None:
        self._client = client
        self._deployment = deployment
        self._settings = settings
        self._max_tokens = max_tokens
        self._is_gpt5 = deployment.startswith("gpt-5")
        # Deterministic post-review hygiene (see agents.plan_hygiene): restore a
        # grounded business key the reviewer re-keyed (Exp 4), and prune links it
        # left invalid or over-produced.
        self._preserve_business_keys = preserve_business_keys
        self._link_parsimony = link_parsimony
        # Same payload hygiene the generator applies — the reviewer emits the
        # final plan, so it must not re-introduce key/technical columns.
        self._technical_payload_columns = frozenset(c.lower() for c in technical_payload_columns)

    @property
    def deployment(self) -> str:
        return self._deployment

    def review(self, plan: ModelingPlan, payload: DiscoveryPayload) -> ModelingPlan:
        """Return a reviewed plan, or the original ``plan`` on any failure.

        Small plans are reviewed in a single call. Large plans are reviewed in
        per-hub-group chunks (see :meth:`_review_chunked`) so the model refines
        each slice instead of collapsing the whole plan in one pass.
        """
        chunk_size = getattr(self._settings, "plan_review_chunk_size", 0) or 0
        if chunk_size <= 0 or len(plan.hubs) <= chunk_size:
            reviewed = self._review_once(plan, payload)
        else:
            reviewed = self._review_chunked(plan, payload, chunk_size=chunk_size)
        return self._apply_hygiene(reviewed, original=plan)

    def _apply_hygiene(self, reviewed: ModelingPlan, *, original: ModelingPlan) -> ModelingPlan:
        """Deterministic post-review passes: restore grounded keys, prune links.

        Applied to whatever ``review`` returns — including the original plan on a
        fallback — so the output is always at least as faithful and conformant as
        the input. Pure; no LLM.
        """
        from dbt_builder.src.ai.agents.plan_hygiene import (
            prune_redundant_links,
            restore_business_keys,
        )

        if self._preserve_business_keys:
            reviewed = restore_business_keys(reviewed, original)
        if self._link_parsimony:
            reviewed = prune_redundant_links(reviewed)
        return reviewed

    def _review_once(self, plan: ModelingPlan, payload: DiscoveryPayload) -> ModelingPlan:
        """Single-call review of one (sub-)plan; returns the original on failure."""
        t0 = time.perf_counter()
        try:
            raw = self._call(plan, payload)
        except Exception as exc:  # noqa: BLE001 — never let the reviewer break the run
            _LOG.warning("PlanReviewer call failed (%s); keeping the original plan.", exc)
            return plan

        reviewed = self._parse(raw, system_id=plan.system_id)
        if reviewed is None:
            _LOG.warning("PlanReviewer returned an unusable plan; keeping the original.")
            return plan

        # Guard against a catastrophic review. A legitimate review refines the
        # plan — fixes keys, adds a missed link, splits a satellite — so counts
        # may wobble up or modestly down. But a review that *collapses* the plan
        # (e.g. 24→6 hubs, merging away valid entities) is a defect, not a
        # refinement. Keep the original whenever the reviewer drops more than a
        # sane fraction of any entity class.
        if not _within_shrink_tolerance(plan, reviewed):
            _LOG.warning(
                "PlanReviewer collapsed the plan (hubs %d→%d, links %d→%d, "
                "sats %d→%d); keeping the original plan.",
                len(plan.hubs),
                len(reviewed.hubs),
                len(plan.links),
                len(reviewed.links),
                len(plan.satellites),
                len(reviewed.satellites),
            )
            return plan

        _LOG.info(
            "PlanReviewer (%s) ok in %.1fs: hubs %d→%d, links %d→%d, sats %d→%d",
            self._deployment,
            time.perf_counter() - t0,
            len(plan.hubs),
            len(reviewed.hubs),
            len(plan.links),
            len(reviewed.links),
            len(plan.satellites),
            len(reviewed.satellites),
        )
        return reviewed

    def _review_chunked(
        self, plan: ModelingPlan, payload: DiscoveryPayload, *, chunk_size: int
    ) -> ModelingPlan:
        """Review a large plan in disjoint per-hub-group chunks, then merge.

        Each chunk is a self-contained sub-plan (a slice of hubs, their
        satellites, and the links wholly within that slice) reviewed by the
        normal single-call path — so the per-chunk collapse guard still applies.
        Links that span two chunks can't be judged in isolation, so they pass
        through unreviewed. The merged result is validated; any inconsistency
        falls back to the original plan (review never breaks the run).
        """
        sub_plans, spanning_links = self._chunk_plan(plan, chunk_size=chunk_size)
        reviewed_sub_plans = self._review_each(sub_plans, payload)
        merged = self._merge_reviewed(
            plan.system_id, reviewed_sub_plans, spanning_links, fallback=plan
        )
        _LOG.info(
            "PlanReviewer chunked review (%d chunks): hubs %d→%d, links %d→%d, sats %d→%d",
            len(sub_plans),
            len(plan.hubs),
            len(merged.hubs),
            len(plan.links),
            len(merged.links),
            len(plan.satellites),
            len(merged.satellites),
        )
        return merged

    def _review_each(
        self, sub_plans: list[ModelingPlan], payload: DiscoveryPayload
    ) -> list[ModelingPlan]:
        """Review every chunk sub-plan, concurrently when configured.

        Chunk reviews are independent calls, so they parallelise cleanly. Worker
        count comes from ``plan_review_parallelism`` (0 → one per chunk); the
        result order matches ``sub_plans`` regardless of completion order.
        """
        if not sub_plans:
            return []
        parallelism = getattr(self._settings, "plan_review_parallelism", 0) or 0
        workers = parallelism if parallelism > 0 else len(sub_plans)
        workers = max(1, min(workers, len(sub_plans)))
        if workers == 1:
            return [self._review_once(sp, payload) for sp in sub_plans]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda sp: self._review_once(sp, payload), sub_plans))

    def _chunk_plan(
        self, plan: ModelingPlan, *, chunk_size: int
    ) -> tuple[list[ModelingPlan], list[LinkDecision]]:
        """Partition into per-hub-group sub-plans + the links that span chunks."""
        hubs = sorted(plan.hubs, key=lambda h: h.name.lower())
        hub_groups = [hubs[i : i + chunk_size] for i in range(0, len(hubs), chunk_size)]

        sats_by_hub: dict[str, list[Any]] = {}
        for sat in plan.satellites:
            sats_by_hub.setdefault(sat.parent_hub, []).append(sat)

        sub_plans: list[ModelingPlan] = []
        assigned_link_names: set[str] = set()
        for group in hub_groups:
            group_hub_names = {h.name for h in group}
            group_hash_keys = {h.hash_key for h in group}
            # A link belongs to this chunk only if BOTH/all its FK hubs are in it.
            group_links = [
                ln for ln in plan.links if set(ln.fk_columns) <= group_hash_keys
            ]
            assigned_link_names.update(ln.name for ln in group_links)
            group_sats = [s for h in group for s in sats_by_hub.get(h.name, [])]
            sub_plans.append(
                ModelingPlan(
                    system_id=plan.system_id,
                    hubs=tuple(group),
                    links=tuple(group_links),
                    satellites=tuple(s for s in group_sats if s.parent_hub in group_hub_names),
                )
            )
        spanning_links = [ln for ln in plan.links if ln.name not in assigned_link_names]
        return sub_plans, spanning_links

    def _merge_reviewed(
        self,
        system_id: str,
        reviewed_sub_plans: list[ModelingPlan],
        spanning_links: list[LinkDecision],
        *,
        fallback: ModelingPlan,
    ) -> ModelingPlan:
        """Union reviewed chunks + the unreviewed spanning links into one plan.

        Names are kept unique across kinds (first occurrence wins); satellites
        whose parent hub did not survive are dropped. If the union is somehow
        inconsistent, return ``fallback`` (the original plan).
        """
        hubs: list[Any] = []
        links: list[Any] = []
        sats: list[Any] = []
        used_names: set[str] = set()

        def _claim(name: str) -> bool:
            if name in used_names:
                return False
            used_names.add(name)
            return True

        for sub in reviewed_sub_plans:
            hubs.extend(h for h in sub.hubs if _claim(h.name))
            links.extend(ln for ln in sub.links if _claim(ln.name))
            sats.extend(sub.satellites)  # claimed below, after hubs are known
        for ln in spanning_links:
            if _claim(ln.name):
                links.append(ln)

        hub_names = {h.name for h in hubs}
        deduped_sats: list[Any] = []
        for sat in sats:
            if sat.parent_hub in hub_names and _claim(sat.name):
                deduped_sats.append(sat)

        try:
            return ModelingPlan(
                system_id=system_id,
                hubs=tuple(hubs),
                links=tuple(links),
                satellites=tuple(deduped_sats),
            )
        except ValidationError as exc:
            _LOG.warning(
                "PlanReviewer chunk merge produced an invalid plan (%s); keeping the original.",
                exc,
            )
            return fallback

    # ── internals ───────────────────────────────────────────────────────────

    def _parse(self, raw: str, *, system_id: str) -> ModelingPlan | None:
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            _LOG.warning("PlanReviewer reply is not valid JSON (%s).", exc)
            return None
        if not isinstance(data, dict):
            return None
        # Tolerate verbose reviewer output + apply the same payload hygiene (DRY).
        data = _coerce_plan_dict(data, technical_columns=self._technical_payload_columns)
        if isinstance(data, dict):
            data["system_id"] = system_id  # authoritative — reviewer cannot drift it
        try:
            return ModelingPlan.model_validate(data)
        except ValidationError as exc:
            _LOG.warning("PlanReviewer reply failed schema validation (%d errors).", exc.error_count())
            return None

    def _user_prompt(self, plan: ModelingPlan, payload: DiscoveryPayload) -> str:
        # Reuse the modeller's source description + schema hint (DRY), then
        # append the draft plan and the review instruction.
        source = _build_user_prompt(payload)
        draft = plan.model_dump_json(indent=2)
        return (
            f"{source}\n\n"
            "DRAFT PLAN TO REVIEW (correct it; return the full corrected plan, "
            "not a diff):\n"
            f"{draft}"
        )

    def _build_kwargs(self) -> dict[str, Any]:
        if self._is_gpt5:
            kwargs: dict[str, Any] = {
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

    def _call(self, plan: ModelingPlan, payload: DiscoveryPayload) -> str:
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": self._user_prompt(plan, payload)},
            ],
            **self._build_kwargs(),
        )
        return (response.choices[0].message.content or "").strip()


# ── factory ──────────────────────────────────────────────────────────────────


def get_plan_reviewer(*, settings: AISettings | None = None) -> PlanReviewer | None:
    """Build a :class:`PlanReviewer` from settings, or ``None`` when disabled.

    Returns ``None`` (so callers skip review) when ``plan_review_enabled`` is
    false or no reviewer deployment is configured — both are treated as
    "run the generator only", never as errors.
    """
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import get_settings

    cfg = settings or get_settings()
    if not cfg.plan_review_enabled:
        return None
    deployment = (cfg.plan_reviewer_chat_deployment or "").strip()
    if not deployment:
        _LOG.warning(
            "plan_review_enabled is set but plan_reviewer_chat_deployment is empty; "
            "skipping plan review."
        )
        return None
    client = AzureOpenAI(
        azure_endpoint=cfg.azure_openai_endpoint,
        api_key=cfg.azure_openai_api_key.get_secret_value(),
        api_version=cfg.azure_openai_api_version,
        max_retries=cfg.llm_max_retries,
    )
    return PlanReviewer(
        client=client,
        deployment=deployment,
        settings=cfg,
        max_tokens=cfg.plan_reviewer_max_tokens,
        technical_payload_columns=cfg.technical_payload_column_set(),
        preserve_business_keys=bool(getattr(cfg, "reviewer_preserve_business_keys", True)),
        link_parsimony=bool(getattr(cfg, "link_parsimony_enabled", True)),
    )
