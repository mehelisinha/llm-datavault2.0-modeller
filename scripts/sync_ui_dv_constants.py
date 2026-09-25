#!/usr/bin/env python3
"""Regenerate ``ui/src/constants/dv.ts`` from ``domain_constants.py`` (B8)."""

from __future__ import annotations

import json
from pathlib import Path

from dbt_builder.src.ai.domain_constants import (
    CHANGE_CATEGORY_INTENTS,
    CHANGE_CATEGORY_LABELS,
    CHANGE_CATEGORY_VALUES,
    DIFF_LABELS,
    DV_KIND_LABELS,
    DV_PREFIXES,
    PLAN_REVIEW_LABELS,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ui" / "src" / "constants" / "dv.ts"


def _ts_object(name: str, mapping: dict[str, str]) -> str:
    entries = ",\n".join(f'  {json.dumps(k)}: {json.dumps(v)}' for k, v in mapping.items())
    return f"export const {name} = Object.freeze({{\n{entries}\n}} as const);"


def main() -> None:
    categories = ",\n".join(f'  {json.dumps(v)}' for v in CHANGE_CATEGORY_VALUES)
    body = f"""/**
 * Data Vault domain constants — generated from Python (B8).
 *
 * Do not edit by hand. Run:
 *   python scripts/sync_ui_dv_constants.py
 */

{_ts_object("DV_PREFIXES", DV_PREFIXES)}

{_ts_object("DV_KIND_LABELS", DV_KIND_LABELS)}

{_ts_object("DIFF_LABELS", DIFF_LABELS)}

{_ts_object("PLAN_REVIEW_LABELS", PLAN_REVIEW_LABELS)}

export const CHANGE_CATEGORY_VALUES = Object.freeze([
{categories}
] as const);

export type ChangeCategory = (typeof CHANGE_CATEGORY_VALUES)[number];

{_ts_object("CHANGE_CATEGORY_LABELS", CHANGE_CATEGORY_LABELS)}

{_ts_object("CHANGE_CATEGORY_INTENTS", CHANGE_CATEGORY_INTENTS)}

export type DvKind = keyof typeof DV_KIND_LABELS;
"""
    OUT.write_text(body, encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
