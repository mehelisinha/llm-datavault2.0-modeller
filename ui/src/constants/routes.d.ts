/**
 * Centralised route paths.
 *
 * Single source of truth for the URLs the app exposes. TanStack Router
 * generates type-safe route refs from the file tree at build time; this
 * file documents the human-readable paths and is referenced by tests and
 * navigation menus so the strings exist in exactly one place.
 */
export declare const ROUTES: Readonly<{
    readonly root: "/";
    readonly discovery: "/discovery";
    readonly diff: "/diff";
    readonly planReview: "/plan-review";
    readonly generatePreview: "/generate-preview";
    readonly history: "/history";
}>;
export type RoutePath = (typeof ROUTES)[keyof typeof ROUTES];
/** Display label per route, kept next to the path so menus can iterate. */
export declare const ROUTE_LABELS: Readonly<Record<RoutePath, string>>;
export declare const GENERATE_LABELS: Readonly<{
    pageTitle: "YAML Preview";
    pageDescription: "Preview the generated YAML before approval.";
    button: "Generate YAML Preview";
    empty: "Click \"Generate YAML Preview\" to see the output.";
}>;
export declare const HISTORY_LABELS: Readonly<{
    pageTitle: "Plan History";
    pageDescription: "View the audit trail of all plan transitions.";
    noRecords: "No history records found.";
}>;
/** Routes shown in the primary nav, in display order. */
export declare const PRIMARY_NAV: readonly RoutePath[];
