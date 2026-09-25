"""Data-Vault impact taxonomy for a detected schema change (Use Case B, RQ2).

Given a :class:`TableChange` from the deterministic diff, decide its **Data Vault
semantic impact**:

* **additive** — forward-compatible; extends the model without invalidating the
  approved contract (a new table → new hub; a new nullable column → new payload).
* **cosmetic** — no Data-Vault structural consequence (a comment; a reorder; a
  compatible type *widening* such as ``int`` → ``bigint`` on a non-key column).
* **breaking** — invalidates the contract; must **not** be auto-applied (a
  business-key rename/removal; a key-column type change; a removed column; a
  removed/orphaned table; an incompatible type change).

Two classifiers share this taxonomy:

* :func:`rule_based_impact` — the deterministic **baseline**. Coarse by design: it
  cannot judge *type compatibility*, so it treats every type change conservatively
  as breaking. This is the floor the AI layer is measured against (H2b).
* :class:`ImpactClassifier` — an LLM that reasons about the change in context and
  can, for example, tell a widening (``int`` → ``bigint``, cosmetic) from an
  incompatible change (``string`` → ``int``, breaking). **Fail-safe:** on any
  error it falls back to :func:`rule_based_impact`, so it can only match or beat
  the baseline, never crash the pipeline.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.catalog import ChangeCategory, ChangeRisk, TableChange

if TYPE_CHECKING:
    from openai import AzureOpenAI

    from dbt_builder.src.ai.settings import AISettings

_LOG = logging.getLogger(__name__)


class ChangeImpact(str, Enum):
    """Data-Vault semantic impact of a schema change (the classification target)."""

    ADDITIVE = "additive"
    COSMETIC = "cosmetic"
    BREAKING = "breaking"


# Column-diff verbs (see contracts.catalog.ColumnDiff.change).
_ADDED = "added"
_REMOVED = "removed"
_TYPE_CHANGED = "type_changed"


def rule_based_impact(change: TableChange) -> ChangeImpact:
    """Deterministic baseline mapping of a :class:`TableChange` to an impact.

    Conservative on purpose (it cannot assess type compatibility): any removed or
    type-changed column, a high-risk flag, or an orphaned table is treated as
    breaking; a purely additive change or a new table is additive; a no-op is
    cosmetic. This coarseness is what the LLM classifier is measured against.
    """
    if change.category is ChangeCategory.UNCHANGED:
        return ChangeImpact.COSMETIC
    if change.category is ChangeCategory.ORPHANED:
        return ChangeImpact.BREAKING  # a source table disappeared
    if change.risk is ChangeRisk.HIGH:
        return ChangeImpact.BREAKING  # business-key rename / key-column type change
    if change.category is ChangeCategory.NEW:
        return ChangeImpact.ADDITIVE  # a brand-new table → new hub
    verbs = {cd.change for cd in change.column_diffs}
    if _REMOVED in verbs or _TYPE_CHANGED in verbs:
        return ChangeImpact.BREAKING  # can't judge compatibility → conservative
    if _ADDED in verbs:
        return ChangeImpact.ADDITIVE
    return ChangeImpact.COSMETIC


class ImpactVerdict(BaseModel):
    """One classification: the impact label plus a short rationale and its source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    impact: ChangeImpact
    rationale: str = Field(default="", max_length=2000)
    source: str = Field(default="ai", description="'ai' or 'rule' (fallback).")


_SYSTEM_PROMPT = (
    "You are a senior Data Vault 2.0 engineer assessing the impact of a source "
    "schema change on an approved Data Vault model. Classify the change as exactly "
    "one of: 'additive' (forward-compatible, extends without invalidating), "
    "'cosmetic' (no structural Data Vault consequence, e.g. a comment, a reorder, "
    "or a compatible type widening like int->bigint on a non-key column), or "
    "'breaking' (invalidates the contract: business-key rename/removal, key-column "
    "type change, removed column, removed table, or an incompatible type change). "
    "Return STRICT JSON: {\"impact\": \"additive|cosmetic|breaking\", "
    "\"rationale\": \"one sentence\"}. No prose outside the JSON."
)


def _describe_change(change: TableChange) -> str:
    """Render a change as a compact, deterministic prompt fragment."""
    lines = [
        f"table: {change.table_name}",
        f"category: {change.category.value}",
        f"risk: {change.risk.value}",
    ]
    if change.column_diffs:
        cols = "; ".join(
            f"{cd.name}: {cd.change}"
            + (f" ({cd.old_dtype} -> {cd.new_dtype})" if cd.old_dtype or cd.new_dtype else "")
            for cd in change.column_diffs
        )
        lines.append(f"column_changes: {cols}")
    if change.notes:
        lines.append(f"notes: {'; '.join(change.notes)}")
    return "\n".join(lines)


class ImpactClassifier:
    """LLM classifier for schema-change impact; falls back to the rule baseline.

    Parameters
    ----------
    client
        Authenticated Azure OpenAI client, or ``None`` to always use the rule
        baseline (useful for offline runs and the deterministic arm).
    deployment
        Chat deployment name.
    settings
        :class:`AISettings`; reads ``llm_seed`` for determinism.
    """

    def __init__(
        self,
        *,
        client: AzureOpenAI | None,
        deployment: str = "",
        settings: AISettings | None = None,
        max_tokens: int = 512,
    ) -> None:
        self._client = client
        self._deployment = deployment
        self._settings = settings
        self._max_tokens = max_tokens
        self._is_gpt5 = deployment.startswith("gpt-5")

    def classify(self, change: TableChange) -> ImpactVerdict:
        """Return an :class:`ImpactVerdict` for ``change`` (rule fallback on any failure)."""
        if self._client is None or not self._deployment:
            return ImpactVerdict(
                impact=rule_based_impact(change), rationale="no LLM configured", source="rule"
            )
        try:
            raw = self._call(change)
            verdict = self._parse(raw)
        except Exception as exc:  # noqa: BLE001 — never let classification break the run
            _LOG.warning("ImpactClassifier failed (%s); using rule baseline.", exc)
            verdict = None
        if verdict is None:
            return ImpactVerdict(
                impact=rule_based_impact(change), rationale="LLM parse failed", source="rule"
            )
        return verdict

    # ── internals ─────────────────────────────────────────────────────────────

    def _parse(self, raw: str) -> ImpactVerdict | None:
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict) or "impact" not in data:
            return None
        try:
            impact = ChangeImpact(str(data["impact"]).strip().lower())
        except ValueError:
            return None
        return ImpactVerdict(
            impact=impact, rationale=str(data.get("rationale", ""))[:2000], source="ai"
        )

    def _build_kwargs(self) -> dict:
        if self._is_gpt5:
            kwargs: dict = {"temperature": 1.0, "max_completion_tokens": self._max_tokens}
        else:
            kwargs = {"temperature": 0.0, "max_tokens": self._max_tokens}
        kwargs["response_format"] = {"type": "json_object"}
        seed = getattr(self._settings, "llm_seed", -1)
        if seed is not None and seed >= 0:
            kwargs["seed"] = seed
        return kwargs

    def _call(self, change: TableChange) -> str:
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _describe_change(change)},
            ],
            **self._build_kwargs(),
        )
        return (response.choices[0].message.content or "").strip()


def get_impact_classifier(*, settings: AISettings | None = None) -> ImpactClassifier:
    """Build an :class:`ImpactClassifier` from settings (rule-only if unconfigured)."""
    from dbt_builder.src.ai.settings import get_settings

    cfg = settings or get_settings()
    deployment = (
        getattr(cfg, "modeller_chat_deployment", "")
        or getattr(cfg, "primary_chat_deployment", "")
        or ""
    ).strip()
    if not deployment:
        return ImpactClassifier(client=None, settings=cfg)
    try:
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=cfg.azure_openai_endpoint,
            api_key=cfg.azure_openai_api_key.get_secret_value(),
            api_version=cfg.azure_openai_api_version,
            max_retries=cfg.llm_max_retries,
        )
    except Exception as exc:  # noqa: BLE001 — unconfigured creds → rule-only
        _LOG.warning("ImpactClassifier: no LLM client (%s); rule-only.", exc)
        return ImpactClassifier(client=None, settings=cfg)
    return ImpactClassifier(client=client, deployment=deployment, settings=cfg)


__all__ = [
    "ChangeImpact",
    "ImpactClassifier",
    "ImpactVerdict",
    "get_impact_classifier",
    "rule_based_impact",
]
