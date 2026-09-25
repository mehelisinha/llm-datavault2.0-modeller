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
  login: "/login",
  discovery: "/discovery",
  diff: "/diff",
  pipelineRun: "/pipeline-run",
  planReview: "/plan-review",
  generatePreview: "/generate-preview",
  history: "/history",
} as const);

export type RoutePath = (typeof ROUTES)[keyof typeof ROUTES];

/** Display label per route, kept next to the path so menus can iterate. */
export const ROUTE_LABELS: Readonly<Record<RoutePath, string>> = Object.freeze({
  [ROUTES.root]: "Home",
  [ROUTES.login]: "Sign in",
  [ROUTES.discovery]: "Generate Vault",
  [ROUTES.diff]: "Diff (advanced)",
  [ROUTES.pipelineRun]: "Pipeline run",
  [ROUTES.planReview]: "Plan review",
  [ROUTES.generatePreview]: "Generate YAML",
  [ROUTES.history]: "History",
});

/** Default entry: pick catalog/schemas and run the full agentic pipeline. */
export const PRIMARY_NAV: readonly RoutePath[] = Object.freeze([
  ROUTES.discovery,
  ROUTES.history,
]);

/** Step-by-step workflow for debugging and manual review (no full pipeline). */
export const ADVANCED_NAV: readonly RoutePath[] = Object.freeze([
  ROUTES.diff,
  ROUTES.planReview,
  ROUTES.generatePreview,
]);

/** Copy for cross-page workflow hints in the advanced path. */
export const WORKFLOW_LABELS = Object.freeze({
  advancedNavGroup: "Advanced",
  discoveryAdvancedSummary:
    "Inspect the bronze diff step-by-step before spending on the LLM, or debug a single stage.",
  discoveryAdvancedSteps:
    "Run snapshot → Diff → Analyze → Validate → Plan review → Generate YAML",
  continueToPlanReview: "Continue to plan review",
  continueToGenerateYaml: "Continue to generate YAML",
  diffWorkflowHint:
    "Advanced workflow: review the change set, then analyze and validate the plan before generating YAML.",
  planWorkflowHint: "Review hubs, links, and satellites, then run the BV architect if needed.",
  generateWorkflowHint:
    "Generate the metadata YAML, download it, and submit for approval when validation passes.",
  backToGenerateVault: "Back to Generate Vault",
} as const);

export const GENERATE_LABELS = Object.freeze({
  pageTitle: "Generate YAML (advanced)",
  pageDescription: "Step 3: render metadata YAML, download, and submit for approval.",
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
  scopeMineLabel: "My history",
  scopeAllLabel: "All users",
  adminOnlyHint: "Visible to admins only.",
} as const);

export const LOGIN_LABELS = Object.freeze({
  pageTitle: "Sign in",
  signInButton: "Sign in with Microsoft",
  signingIn: "Signing in…",
  disabledHint:
    "Microsoft sign-in is not configured for this deployment. Ask an admin to set the VITE_MSAL_* environment variables.",
  devModeHint: "Running in development mode — using VITE_DEV_ACTOR for identity.",
  continueDev: "Continue in development mode",
  legal: "By signing in you agree to your organisation's acceptable-use policy.",
} as const);