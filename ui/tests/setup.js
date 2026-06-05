import { createElement } from "react";
import { vi } from "vitest";
/**
 * Vitest setup — extends `expect` with jest-dom matchers and silences
 * the act warning that React 18 strict mode emits during test renders.
 */
import "@testing-library/jest-dom/vitest";
vi.mock("@tanstack/react-router", async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual,
        Link: ({ children, to, className, ...rest }) => createElement("a", { href: String(to), className, ...rest }, children),
        useNavigate: () => vi.fn(),
    };
});
