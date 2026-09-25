"""Data Vault 2.0 conformance scorer — a ground-truth-free quality metric.

The thesis needs to measure model quality without a hand-labelled reference for
every source system. This module scores a :class:`ModelingPlan` against the
objective DV2 conventions the modeller is *instructed* to follow (the same rules
encoded in ``modeller._BUILTIN_RV_RULES``), turning each into a mechanical
check. It emits:

* a scalar **conformance score** (fraction of checks passed), and
* a typed list of **issues** whose ``IssueType`` gives the error-taxonomy
  distribution the ablation / learning-curve study reports.

Pure and deterministic: no I/O, no LLM, reproducible for an identical plan.
It measures *convention conformance*, not semantic correctness — the latter is
what the gold-set precision/recall (Phase 5) and human review capture.
"""

from __future__ import annotations

from collections import Counter
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from dbt_builder.src.ai.contracts.decisions import ModelingPlan

# Business-key names that are physical surrogates rather than semantic keys.
# A hub keyed ONLY on one of these (or an ``*_id`` / ``*_sk`` column) failed the
# "prefer a real business key" rule. Lower-cased for case-insensitive matching.
_SURROGATE_KEYS = frozenset({"id", "sys_id", "guid", "uuid", "pk", "oid", "sk", "rowid"})
_SURROGATE_SUFFIXES = ("_id", "_sk", "_key", "_guid", "_uuid")


class IssueType(str, Enum):
    """Taxonomy of DV2 convention violations (the study's error categories)."""

    NAMING = "naming"  # missing hub_/link_/sat_ prefix
    HASH_KEY_NAMING = "hash_key_naming"  # hash key not HK_ / hashdiff not HD_
    SURROGATE_BUSINESS_KEY = "surrogate_business_key"  # hub keyed on a surrogate
    LINK_UNDER_TWO_HUBS = "link_under_two_hubs"  # link relates < 2 hubs
    LINK_FK_UNRESOLVED = "link_fk_unresolved"  # fk hash key matches no hub
    SATELLITE_ORPHAN = "satellite_orphan"  # parent hub not in the plan
    SATELLITE_EMPTY_PAYLOAD = "satellite_empty_payload"  # nothing descriptive
    PAYLOAD_KEY_LEAK = "payload_key_leak"  # a business key sits in a sat payload
    HUB_WITHOUT_SATELLITE = "hub_without_satellite"  # no descriptive history
    EMPTY_PLAN = "empty_plan"  # no hubs at all


class ConformanceIssue(BaseModel):
    """One failed convention check, attributed to a plan object."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: IssueType
    object_name: str = Field(
        description="Plan object the issue is attributed to ('' = plan-level)."
    )
    message: str


class ConformanceReport(BaseModel):
    """Result of scoring one plan: scalar score + typed issue list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    checks_total: int = Field(ge=0)
    checks_passed: int = Field(ge=0)
    issues: tuple[ConformanceIssue, ...] = ()

    @property
    def score(self) -> float:
        """Fraction of checks passed in ``[0, 1]`` (1.0 when no checks ran)."""
        return 1.0 if self.checks_total == 0 else self.checks_passed / self.checks_total

    @property
    def issues_by_type(self) -> dict[str, int]:
        """Error-taxonomy histogram — the per-category counts the study reports."""
        counts = Counter(i.type.value for i in self.issues)
        return {t.value: counts.get(t.value, 0) for t in IssueType}


def _is_surrogate_only(business_keys: tuple[str, ...]) -> bool:
    """True when every business key is a physical surrogate (no semantic key)."""
    if not business_keys:
        return False
    for key in business_keys:
        low = key.lower()
        if low in _SURROGATE_KEYS or low.endswith(_SURROGATE_SUFFIXES):
            continue
        return False  # found at least one semantic key → not surrogate-only
    return True


class _Scorer:
    """Accumulates check pass/fail counts and issues for one plan."""

    def __init__(self) -> None:
        self.total = 0
        self.passed = 0
        self.issues: list[ConformanceIssue] = []

    def check(self, ok: bool, itype: IssueType, obj: str, message: str) -> None:
        self.total += 1
        if ok:
            self.passed += 1
        else:
            self.issues.append(ConformanceIssue(type=itype, object_name=obj, message=message))


def score_plan(
    plan: ModelingPlan, *, technical_columns: frozenset[str] = frozenset()
) -> ConformanceReport:
    """Score ``plan`` against DV2 conventions; return a :class:`ConformanceReport`.

    ``technical_columns`` (lower-cased) are load/audit/CDC columns that must not
    appear in a satellite payload; supply the same set the modeller strips so the
    leak check matches production behaviour.
    """
    s = _Scorer()
    tech = frozenset(c.lower() for c in technical_columns)

    hub_names = {h.name for h in plan.hubs}
    hash_key_to_bks = {
        h.hash_key: frozenset(bk.lower() for bk in h.business_keys) for h in plan.hubs
    }
    bk_by_hub = {h.name: frozenset(bk.lower() for bk in h.business_keys) for h in plan.hubs}
    hubs_with_sat = {s_.parent_hub for s_ in plan.satellites}

    # Plan-level: a raw vault without hubs is degenerate.
    s.check(bool(plan.hubs), IssueType.EMPTY_PLAN, "", "plan has no hubs")

    for hub in plan.hubs:
        s.check(
            hub.name.startswith("hub_"), IssueType.NAMING, hub.name, "hub name lacks 'hub_' prefix"
        )
        s.check(
            hub.hash_key.startswith("HK_"),
            IssueType.HASH_KEY_NAMING,
            hub.name,
            "hub hash key lacks 'HK_' prefix",
        )
        s.check(
            not _is_surrogate_only(hub.business_keys),
            IssueType.SURROGATE_BUSINESS_KEY,
            hub.name,
            f"hub keyed only on surrogate(s) {list(hub.business_keys)}",
        )
        s.check(
            hub.name in hubs_with_sat,
            IssueType.HUB_WITHOUT_SATELLITE,
            hub.name,
            "hub has no descriptive satellite",
        )

    for link in plan.links:
        s.check(
            link.name.startswith("link_"),
            IssueType.NAMING,
            link.name,
            "link name lacks 'link_' prefix",
        )
        s.check(
            link.hash_key.startswith("HK_"),
            IssueType.HASH_KEY_NAMING,
            link.name,
            "link hash key lacks 'HK_' prefix",
        )
        s.check(
            len(link.fk_columns) >= 2,
            IssueType.LINK_UNDER_TWO_HUBS,
            link.name,
            f"link relates {len(link.fk_columns)} hub(s); expected >= 2",
        )
        unresolved = [fk for fk in link.fk_columns if fk not in hash_key_to_bks]
        s.check(
            not unresolved,
            IssueType.LINK_FK_UNRESOLVED,
            link.name,
            f"link fk hash key(s) match no hub: {unresolved}",
        )

    for sat in plan.satellites:
        s.check(
            sat.name.startswith(("sat_", "eff_sat_")),
            IssueType.NAMING,
            sat.name,
            "satellite name lacks 'sat_'/'eff_sat_' prefix",
        )
        s.check(
            sat.hashdiff.startswith("HD_"),
            IssueType.HASH_KEY_NAMING,
            sat.name,
            "satellite hashdiff lacks 'HD_' prefix",
        )
        s.check(
            sat.parent_hub in hub_names,
            IssueType.SATELLITE_ORPHAN,
            sat.name,
            f"satellite parent hub '{sat.parent_hub}' not in plan",
        )
        s.check(
            bool(sat.payload),
            IssueType.SATELLITE_EMPTY_PAYLOAD,
            sat.name,
            "satellite payload is empty",
        )
        # Payload must not carry the parent hub's business key or a technical col.
        own_bk = bk_by_hub.get(sat.parent_hub, frozenset())
        leaked = [c for c in sat.payload if c.lower() in own_bk or c.lower() in tech]
        s.check(
            not leaked,
            IssueType.PAYLOAD_KEY_LEAK,
            sat.name,
            f"satellite payload leaks key/technical column(s): {leaked}",
        )

    return ConformanceReport(checks_total=s.total, checks_passed=s.passed, issues=tuple(s.issues))


__all__ = ["ConformanceIssue", "ConformanceReport", "IssueType", "score_plan"]
