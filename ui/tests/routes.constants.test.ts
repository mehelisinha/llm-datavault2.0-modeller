import { describe, expect, it } from "vitest";

import {
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

  it("primary nav surfaces the consolidated pipeline-run workflow", () => {
    expect(PRIMARY_NAV).toContain(ROUTES.pipelineRun);
  });
});
