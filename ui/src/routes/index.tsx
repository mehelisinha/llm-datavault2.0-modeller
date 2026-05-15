import { createRoute, redirect } from "@tanstack/react-router";

import { PageShell } from "@/components/PageShell";
import { PlaceholderCard } from "@/components/PlaceholderCard";
import { ROUTES } from "@/constants/routes";

import { rootRoute } from "./root";

/**
 * Code-based route definitions.
 *
 * One factory per route, all parented to `rootRoute`. Pages currently
 * compose the shared `PlaceholderCard`; B6.4+ replace the body with real
 * page logic. The placeholder copy lives inline so each route advertises
 * which sub-phase fills it in.
 */

const PLACEHOLDER_PHASES = Object.freeze({
  discovery: "B6.4",
  diff: "B6.5",
  planReview: "B6.5",
  generatePreview: "B6.5",
  history: "B6.5",
} as const);

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.root,
  beforeLoad: () => {
    throw redirect({ to: ROUTES.discovery });
  },
});

export const discoveryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.discovery,
  component: () => (
    <PageShell
      title="Discovery"
      description="Pick a catalog and schema, snapshot bronze, and prepare a change set."
    >
      <PlaceholderCard
        title="Catalog inspection"
        description="Connects to Unity Catalog and stages a bronze snapshot for diffing."
        upcomingPhase={PLACEHOLDER_PHASES.discovery}
      />
    </PageShell>
  ),
});

export const diffRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.diff,
  component: () => (
    <PageShell
      title="Diff"
      description="Review change-set rows and choose actionable tables."
    >
      <PlaceholderCard
        title="Change set"
        description="NEW / SCHEMA_CHANGED / UNCHANGED / ORPHANED rows from `read_bronze`."
        upcomingPhase={PLACEHOLDER_PHASES.diff}
      />
    </PageShell>
  ),
});

export const planReviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.planReview,
  component: () => (
    <PageShell
      title="Plan review"
      description="Inspect hubs, satellites, links, and BV proposals before generation."
    >
      <PlaceholderCard
        title="Modelling plan"
        description="Hub / satellite / link / PIT / bridge layout from the agents pipeline."
        upcomingPhase={PLACEHOLDER_PHASES.planReview}
      />
    </PageShell>
  ),
});

export const generatePreviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.generatePreview,
  component: () => (
    <PageShell
      title="Generate preview"
      description="Render YAML files deterministically and review before submit."
    >
      <PlaceholderCard
        title="YAML bundle"
        description="Deterministic per-file output ready for review and approval."
        upcomingPhase={PLACEHOLDER_PHASES.generatePreview}
      />
    </PageShell>
  ),
});

export const historyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.history,
  component: () => (
    <PageShell
      title="History"
      description="Audit log of past plans, decisions, and reviewer activity."
    >
      <PlaceholderCard
        title="Audit log"
        description="Plans, decisions, and approvals recorded by `SqliteApprovalStore`."
        upcomingPhase={PLACEHOLDER_PHASES.history}
      />
    </PageShell>
  ),
});

/** All non-root routes parented under `rootRoute`. */
export const routeTree = rootRoute.addChildren([
  indexRoute,
  discoveryRoute,
  diffRoute,
  planReviewRoute,
  generatePreviewRoute,
  historyRoute,
]);

