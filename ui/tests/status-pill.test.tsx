import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusPill } from "@/components/ui";
import { CHANGE_CATEGORIES, type ChangeCategory } from "@/constants/dv";

const INTENT_BY_CATEGORY: Readonly<Record<ChangeCategory, string>> = {
  NEW: "bg-success",
  SCHEMA_CHANGED: "bg-warning",
  UNCHANGED: "bg-secondary",
  ORPHANED: "bg-destructive",
};

describe("StatusPill", () => {
  it.each(CHANGE_CATEGORIES)("renders %s with the right intent class", (category) => {
    render(<StatusPill category={category} />);
    const pill = screen.getByText(category);
    expect(pill.className).toContain(INTENT_BY_CATEGORY[category]);
  });
});
