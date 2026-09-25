import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle, } from "@/components/ui";
describe("Card", () => {
    it("composes header / title / description / content / footer", () => {
        render(_jsxs(Card, { "data-testid": "card", children: [_jsxs(CardHeader, { children: [_jsx(CardTitle, { children: "Title" }), _jsx(CardDescription, { children: "Desc" })] }), _jsx(CardContent, { children: "Body" }), _jsx(CardFooter, { children: "Footer" })] }));
        expect(screen.getByTestId("card").className).toContain("rounded-lg");
        expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
        expect(screen.getByText("Desc")).toBeInTheDocument();
        expect(screen.getByText("Body")).toBeInTheDocument();
        expect(screen.getByText("Footer")).toBeInTheDocument();
    });
});
