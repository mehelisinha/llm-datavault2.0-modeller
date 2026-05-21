/**
 * Centralised route paths.
 *
 * Single source of truth for the URLs the app exposes. TanStack Router
 * generates type-safe route refs from the file tree at build time; this
 * file documents the human-readable paths and is referenced by tests and
 * navigation menus so the strings exist in exactly one place.
 */
export const ROUTES = Object.freeze({
  root: "/",
  discovery: "/discovery",
  diff: "/diff",
  planReview: "/plan-review",
  generatePreview: "/generate-preview",
  history: "/history",
} as const);

export type RoutePath = (typeof ROUTES)[keyof typeof ROUTES];

/** Display label per route, kept next to the path so menus can iterate. */
export const ROUTE_LABELS: Readonly<Record<RoutePath, string>> = Object.freeze({
  [ROUTES.root]: "Home",
  [ROUTES.discovery]: "Discovery",
  [ROUTES.diff]: "Diff",
  [ROUTES.planReview]: "Plan review",
  [ROUTES.generatePreview]: "Generate preview",
  [ROUTES.history]: "History",
});

/** Routes shown in the primary nav, in display order. */
export const PRIMARY_NAV: readonly RoutePath[] = Object.freeze([
  ROUTES.discovery,
  ROUTES.diff,
  ROUTES.planReview,
  ROUTES.generatePreview,
  ROUTES.history,
]);

export const GENERATE_LABELS = Object.freeze({
  pageTitle: "YAML Preview",
  pageDescription: "Preview the generated YAML before approval.",
  button: "Generate YAML Preview",
  empty: 'Click "Generate YAML Preview" to see the output.',
  previewCardTitle: "Generated YAML",
  noSystemWarning:
    "No source system metadata is available. YAML can still be generated from the plan.",
  noPlanHint: "Run the schema analyzer on the Diff page first.",
  download: "Download YAML",
  downloadDisabledHint: "Generate YAML first",
  downloadFilename: (systemId: string) => `${systemId || "metadata"}.yaml`,
} as const);

export const HISTORY_LABELS = Object.freeze({
  pageTitle: "Plan History",
  pageDescription: "View the audit trail of all plan transitions.",
  noRecords: "No history records found.",
} as const);
