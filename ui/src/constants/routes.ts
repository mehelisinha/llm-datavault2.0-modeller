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
