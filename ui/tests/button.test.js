import { jsx as _jsx } from "react/jsx-runtime";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "@/components/ui";
describe("Button", () => {
    it("renders children and defaults to type=button", () => {
        render(_jsx(Button, { children: "Save" }));
        const btn = screen.getByRole("button", { name: "Save" });
        expect(btn).toHaveAttribute("type", "button");
    });
    it("respects an explicit type=submit", () => {
        render(_jsx(Button, { type: "submit", children: "Go" }));
        expect(screen.getByRole("button", { name: "Go" })).toHaveAttribute("type", "submit");
    });
    it("applies the destructive intent classes", () => {
        render(_jsx(Button, { intent: "destructive", children: "Delete" }));
        const btn = screen.getByRole("button", { name: "Delete" });
        expect(btn.className).toContain("bg-destructive");
    });
    it("applies the icon size classes", () => {
        render(_jsx(Button, { size: "icon", "aria-label": "open" }));
        const btn = screen.getByRole("button", { name: "open" });
        expect(btn.className).toContain("h-9");
        expect(btn.className).toContain("w-9");
    });
    it("forwards click events", async () => {
        const onClick = vi.fn();
        render(_jsx(Button, { onClick: onClick, children: "Click" }));
        screen.getByRole("button", { name: "Click" }).click();
        expect(onClick).toHaveBeenCalledOnce();
    });
    it("renders left and right icon slots", () => {
        render(_jsx(Button, { leftIcon: _jsx("span", { "data-testid": "left" }), rightIcon: _jsx("span", { "data-testid": "right" }), children: "Label" }));
        expect(screen.getByTestId("left")).toBeInTheDocument();
        expect(screen.getByTestId("right")).toBeInTheDocument();
    });
});
