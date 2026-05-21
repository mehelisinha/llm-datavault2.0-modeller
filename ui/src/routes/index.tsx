import { createRoute, redirect } from "@tanstack/react-router";

import { ROUTES } from "@/constants/routes";
import DiscoveryPage from "@/pages/Discovery";
import DiffReviewPage from "@/pages/DiffReview";
import PlanReviewPage from "@/pages/PlanReview";
import GeneratePreviewPage from "@/pages/GeneratePreview";
import HistoryPage from "@/pages/History";

import { rootRoute } from "./root";

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
  component: DiscoveryPage,
});

export const diffRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.diff,
  component: DiffReviewPage,
});

export const planReviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.planReview,
  component: PlanReviewPage,
});

export const generatePreviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.generatePreview,
  component: GeneratePreviewPage,
});

export const historyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: ROUTES.history,
  component: HistoryPage,
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
