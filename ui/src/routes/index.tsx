import { createRoute, redirect } from "@tanstack/react-router";
import type { ComponentType } from "react";

import { RequireAuth } from "@/components/RequireAuth";
import { ROUTES } from "@/constants/routes";
import DiscoveryPage from "@/pages/Discovery";
import DiffReviewPage from "@/pages/DiffReview";
import LoginPage from "@/pages/Login";
import PipelineRunPage from "@/pages/PipelineRunPage";
import PlanReviewPage from "@/pages/PlanReview";
import GeneratePreviewPage from "@/pages/GeneratePreview";
import HistoryPage from "@/pages/History";

import { rootRoute } from "./root";

/** DRY wrapper so every page gets the same auth gate without per-route boilerplate. */
function gated(Page: ComponentType): () => JSX.Element {
  const Guarded = () => (
    <RequireAuth>
      <Page />
    </RequireAuth>
  );
  Guarded.displayName = `Gated(${Page.displayName ?? Page.name ?? "Page"})`;
  return Guarded;
}

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.root,
  beforeLoad: () => {
    throw redirect({ to: ROUTES.discovery });
  },
});

export const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.login,
  component: LoginPage,
});

export const discoveryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.discovery,
  component: gated(DiscoveryPage),
});

export const diffRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.diff,
  component: gated(DiffReviewPage),
});

export const pipelineRunRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.pipelineRun,
  component: gated(PipelineRunPage),
});

export const planReviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.planReview,
  component: gated(PlanReviewPage),
});

export const generatePreviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.generatePreview,
  component: gated(GeneratePreviewPage),
});

export const historyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.history,
  component: gated(HistoryPage),
});

/** All non-root routes parented under `rootRoute`. */
export const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  discoveryRoute,
  diffRoute,
  pipelineRunRoute,
  planReviewRoute,
  generatePreviewRoute,
  historyRoute,
]);