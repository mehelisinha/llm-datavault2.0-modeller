"""Canonical DV domain constants — single source for UI sync (B8).

Imported by ``scripts/sync_ui_dv_constants.py`` to regenerate the
TypeScript mirror under ``ui/src/constants/dv.ts``.
"""

from __future__ import annotations

DV_PREFIXES: dict[str, str] = {
    "hub": "hub_",
    "satellite": "sat_",
    "link": "link_",
    "staging": "stg_",
    "pit": "pit_",
    "bridge": "br_",
}

DV_KIND_LABELS: dict[str, str] = {
    "hub": "Hub",
    "satellite": "Satellite",
    "link": "Link",
    "pit": "Point-in-Time",
    "bridge": "Bridge",
    "bv_satellite": "BV Satellite",
}

# Mirrors ``ChangeCategory`` in contracts/catalog.py (serialized values).
CHANGE_CATEGORY_VALUES: tuple[str, ...] = ("new", "drift", "unchanged", "orphaned")

CHANGE_CATEGORY_LABELS: dict[str, str] = {
    "new": "New",
    "drift": "Schema changed",
    "unchanged": "Unchanged",
    "orphaned": "Orphaned",
}

CHANGE_CATEGORY_INTENTS: dict[str, str] = {
    "new": "success",
    "drift": "warning",
    "unchanged": "neutral",
    "orphaned": "destructive",
}

DIFF_LABELS: dict[str, str] = {
    "pageTitle": "Plan Diff & Review",
    "pageDescription": "Review the change set, run analysis, and approve or request changes.",
    "noChanges": "No changes in this category.",
    "validationSummary": "Validation Summary",
    "errors": "Errors:",
    "warnings": "Warnings:",
    "infos": "Infos:",
    "analyze": "Run schema analyzer",
    "validate": "Validate plan",
}

PLAN_REVIEW_LABELS: dict[str, str] = {
    "pageTitle": "Plan review",
    "pageDescription": "Inspect hubs, satellites, links, and BV proposals before generation.",
    "runArchitect": "Run BV architect",
    "empty": "Run the schema analyzer on the Diff page first.",
}
