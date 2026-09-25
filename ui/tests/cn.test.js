import { describe, expect, it } from "vitest";
import { cn } from "@/lib/cn";
describe("cn", () => {
    it("joins truthy parts with single spaces", () => {
        expect(cn("a", "b", "c")).toBe("a b c");
    });
    it("drops falsy values", () => {
        expect(cn("a", false, null, undefined, "b")).toBe("a b");
    });
    it("flattens arrays and conditional objects via clsx", () => {
        expect(cn(["a", "b"], { c: true, d: false })).toBe("a b c");
    });
    it("resolves conflicting Tailwind utilities (last-wins)", () => {
        expect(cn("p-2", "p-4")).toBe("p-4");
        expect(cn("text-sm text-muted-foreground", "text-foreground")).toBe("text-sm text-foreground");
    });
});
