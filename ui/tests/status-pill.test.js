import { jsx as _jsx } from "react/jsx-runtime";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusPill } from "@/components/ui";
import { CHANGE_CATEGORY_LABELS, CHANGE_CATEGORY_VALUES, } from "@/constants/dv";
describe("StatusPill", () => {
    it.each(CHANGE_CATEGORY_VALUES)("renders %s label", (category) => {
        render(_jsx(StatusPill, { category: category }));
        expect(screen.getByText(CHANGE_CATEGORY_LABELS[category])).toBeInTheDocument();
    });
});
