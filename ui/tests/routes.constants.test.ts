import { describe, expect, it } from "vitest";

import {
  ADVANCED_NAV,
  PRIMARY_NAV,
  ROUTES,
  ROUTE_LABELS,
  type RoutePath,
} from "@/constants/routes";

describe("ROUTES", () => {
  it("exposes a label for every path", () => {
    for (const path of Object.values(ROUTES) as RoutePath[]) {
      expect(ROUTE_LABELS[path]).toBeTruthy();
    }
  });

  it("primary nav entries are all valid non-root routes", () => {
    const nonRoot = new Set(
      (Object.values(ROUTES) as RoutePath[]).filter((p) => p !== ROUTES.root),
    );
    for (const path of PRIMARY_NAV) {
      expect(nonRoot.has(path)).toBe(true);
    }
  });

  it("primary nav is Generate Vault + history only", () => {
    expect(PRIMARY_NAV).toEqual([ROUTES.discovery, ROUTES.history]);
    expect(PRIMARY_NAV).not.toContain(ROUTES.pipelineRun);
  });

  it("advanced nav lists the step-by-step workflow pages", () => {
    expect(ADVANCED_NAV).toEqual([
      ROUTES.diff,
      ROUTES.planReview,
      ROUTES.generatePreview,
    ]);
  });
});
