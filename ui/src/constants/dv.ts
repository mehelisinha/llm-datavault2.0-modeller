/**
 * Data Vault domain constants — generated from Python (B8).
 *
 * Do not edit by hand. Run:
 *   python scripts/sync_ui_dv_constants.py
 */

export const DV_PREFIXES = Object.freeze({
  "hub": "hub_",
  "satellite": "sat_",
  "link": "link_",
  "staging": "stg_",
  "pit": "pit_",
  "bridge": "br_"
} as const);

export const DV_KIND_LABELS = Object.freeze({
  "hub": "Hub",
  "satellite": "Satellite",
  "link": "Link",
  "pit": "Point-in-Time",
  "bridge": "Bridge",
  "bv_satellite": "BV Satellite"
} as const);

export const DIFF_LABELS = Object.freeze({
  "pageTitle": "Plan Diff & Review",
  "pageDescription": "Review the change set, run analysis, and approve or request changes.",
  "noChanges": "No changes in this category.",
  "validationSummary": "Validation Summary",
  "errors": "Errors:",
  "warnings": "Warnings:",
  "infos": "Infos:",
  "analyze": "Run schema analyzer",
  "validate": "Validate plan"
} as const);

export const PLAN_REVIEW_LABELS = Object.freeze({
  "pageTitle": "Plan review",
  "pageDescription": "Inspect hubs, satellites, links, and BV proposals before generation.",
  "runArchitect": "Run BV architect",
  "empty": "Run the schema analyzer on the Diff page first."
} as const);

export const CHANGE_CATEGORY_VALUES = Object.freeze([
  "new",
  "drift",
  "unchanged",
  "orphaned"
] as const);

export type ChangeCategory = (typeof CHANGE_CATEGORY_VALUES)[number];

export const CHANGE_CATEGORY_LABELS = Object.freeze({
  "new": "New",
  "drift": "Schema changed",
  "unchanged": "Unchanged",
  "orphaned": "Orphaned"
} as const);

export const CHANGE_CATEGORY_INTENTS = Object.freeze({
  "new": "success",
  "drift": "warning",
  "unchanged": "neutral",
  "orphaned": "destructive"
} as const);

export type DvKind = keyof typeof DV_KIND_LABELS;

// ── Hand-written labels (not yet sourced from Python). ─────────────────────
// TODO(cleanup): extend `scripts/sync_ui_dv_constants.py` to emit these too,
// or move them to a dedicated `constants/approval.ts` file so the auto-
// generated section above stays untouched by the sync script.
export const APPROVAL_LABELS = Object.freeze({
  section: "Decision",
  submitLabel: "Submit for review",
  commentLabel: "Review comment",
  commentPlaceholder: "Optional for approve; required for reject and request-changes",
  approve: "Approve",
  reject: "Reject",
  requestChanges: "Request changes",
  submitNeeded: "Submit the plan for review first to enable approval actions.",
  validationBlock: "Validation must show zero ERROR issues before approval is allowed.",
  approveSuccess: "Plan approved",
  approveError: "Approval failed",
  rejectSuccess: "Plan rejected",
  rejectError: "Reject failed",
  requestChangesSuccess: "Changes requested",
  requestChangesError: "Request changes failed",
  submitSuccess: "Submitted for review",
  submitError: "Submit failed",
  generateSuccess: "YAML preview generated",
  generateError: "YAML generation failed",
  analyzeSuccess: "Schema analyzer complete",
  analyzeError: "Schema analyzer failed",
  validateSuccess: "Validation complete",
  validateError: "Validation failed",
} as const);
