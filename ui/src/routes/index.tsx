import { createRoute, redirect } from "@tanstack/react-router";

import { PageShell } from "@/components/PageShell";
import { ROUTES } from "@/constants/routes";

import { rootRoute } from "./root";

/**
 * Code-based route definitions.
 *
 * One factory per route, all parented to `rootRoute`. Pages currently render
 * placeholder shells; B6.5 fills in the real interactions. Keeping the page
 * components inline avoids one-file-per-shell boilerplate while leaving an
 * obvious extraction point once a page grows beyond ~80 LOC.
 */

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
      <p className="text-sm text-slate-500">
        UI for this step lands in B6.5 — wiring `inspect_catalog` + `read_bronze`.
      </p>
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
      <p className="text-sm text-slate-500">B6.5 fills this in.</p>
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
      <p className="text-sm text-slate-500">B6.5 fills this in.</p>
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
      <p className="text-sm text-slate-500">B6.5 fills this in.</p>
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
      <p className="text-sm text-slate-500">B6.5 fills this in.</p>
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
