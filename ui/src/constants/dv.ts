/**
 * Data Vault domain constants — mirror of the backend prefixes/labels.
 *
 * Keep this file in sync with `dbt_builder/src/ai/agents/yaml_generator.py`
 * and `dbt_builder/src/ai/agents/bv_architect.py`. A future B8 task may
 * generate this file from the backend; today it's hand-mirrored.
 */

export const DV_PREFIXES = Object.freeze({
  hub: "hub_",
  satellite: "sat_",
  link: "link_",
  staging: "stg_",
  pit: "pit_",
  bridge: "br_",
} as const);

export const DV_KIND_LABELS = Object.freeze({
  hub: "Hub",
  satellite: "Satellite",
  link: "Link",
  pit: "Point-in-Time",
  bridge: "Bridge",
  bv_satellite: "BV Satellite",
} as const);

export type DvKind = keyof typeof DV_KIND_LABELS;

/** Change categories from `ChangeSet` — display order matters in the diff page. */
export const CHANGE_CATEGORIES = Object.freeze([
  "NEW",
  "SCHEMA_CHANGED",
  "UNCHANGED",
  "ORPHANED",
] as const);

export type ChangeCategory = (typeof CHANGE_CATEGORIES)[number];
