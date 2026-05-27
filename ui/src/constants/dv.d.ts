/**
 * Data Vault domain constants — generated from Python (B8).
 *
 * Do not edit by hand. Run:
 *   python scripts/sync_ui_dv_constants.py
 */
export declare const DV_PREFIXES: Readonly<{
    readonly hub: "hub_";
    readonly satellite: "sat_";
    readonly link: "link_";
    readonly staging: "stg_";
    readonly pit: "pit_";
    readonly bridge: "br_";
}>;
export declare const DV_KIND_LABELS: Readonly<{
    readonly hub: "Hub";
    readonly satellite: "Satellite";
    readonly link: "Link";
    readonly pit: "Point-in-Time";
    readonly bridge: "Bridge";
    readonly bv_satellite: "BV Satellite";
}>;
export declare const DIFF_LABELS: Readonly<{
    readonly pageTitle: "Diff (advanced)";
    readonly pageDescription: "Step 1 of the manual workflow: review bronze vs vault, then analyze and validate.";
    readonly noChanges: "No changes in this category.";
    readonly validationSummary: "Validation Summary";
    readonly errors: "Errors:";
    readonly warnings: "Warnings:";
    readonly infos: "Infos:";
    readonly analyze: "Run schema analyzer";
    readonly validate: "Validate plan";
}>;
export declare const PLAN_REVIEW_LABELS: Readonly<{
    readonly pageTitle: "Plan review (advanced)";
    readonly pageDescription: "Step 2: inspect the modelling plan and optional BV proposal before YAML generation.";
    readonly runArchitect: "Run BV architect";
    readonly empty: "Run the schema analyzer on the Diff page first.";
}>;
export declare const CHANGE_CATEGORY_VALUES: readonly ["new", "drift", "unchanged", "orphaned"];
export type ChangeCategory = (typeof CHANGE_CATEGORY_VALUES)[number];
export declare const CHANGE_CATEGORY_LABELS: Readonly<{
    readonly new: "New";
    readonly drift: "Schema changed";
    readonly unchanged: "Unchanged";
    readonly orphaned: "Orphaned";
}>;
export declare const CHANGE_CATEGORY_INTENTS: Readonly<{
    readonly new: "success";
    readonly drift: "warning";
    readonly unchanged: "neutral";
    readonly orphaned: "destructive";
}>;
export type DvKind = keyof typeof DV_KIND_LABELS;
export declare const APPROVAL_LABELS: Readonly<{
    readonly section: "Decision";
    readonly submitLabel: "Submit for review";
    readonly commentLabel: "Review comment";
    readonly commentPlaceholder: "Optional for approve; required for reject and request-changes";
    readonly approve: "Approve";
    readonly reject: "Reject";
    readonly requestChanges: "Request changes";
    readonly submitNeeded: "Submit the plan for review first to enable approval actions.";
    readonly validationBlock: "Validation must show zero ERROR issues before approval is allowed.";
    readonly approveSuccess: "Plan approved";
    readonly approveError: "Approval failed";
    readonly rejectSuccess: "Plan rejected";
    readonly rejectError: "Reject failed";
    readonly requestChangesSuccess: "Changes requested";
    readonly requestChangesError: "Request changes failed";
    readonly submitSuccess: "Submitted for review";
    readonly submitError: "Submit failed";
    readonly generateSuccess: "YAML preview generated";
    readonly generateError: "YAML generation failed";
    readonly analyzeSuccess: "Schema analyzer complete";
    readonly analyzeError: "Schema analyzer failed";
    readonly validateSuccess: "Validation complete";
    readonly validateError: "Validation failed";
}>;
