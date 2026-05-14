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

  it("primary nav contains every non-root route", () => {
    const expected = (Object.values(ROUTES) as RoutePath[]).filter(
      (p) => p !== ROUTES.root,
    );
    expect([...PRIMARY_NAV].sort()).toEqual([...expected].sort());
  });
});
