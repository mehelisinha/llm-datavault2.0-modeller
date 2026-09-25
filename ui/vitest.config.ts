import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
    // Prefer TypeScript sources over the `tsc -b` composite emit
    // (`*.js` / `*.d.ts`) so tests never resolve against stale build artefacts.
    extensions: [".ts", ".tsx", ".mts", ".mjs", ".js", ".jsx", ".json"],
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    // Limit discovery to TypeScript sources so the `tsc -b` composite emit
    // (`*.js` / `*.d.ts`) is never picked up as duplicate suites.
    include: ["tests/**/*.test.{ts,tsx}"],
    css: false,
    restoreMocks: true,
    clearMocks: true,
  },
});
