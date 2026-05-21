/**
 * B8 — UI-side verification matrix (contract smoke).
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
const matrixPath = resolve(import.meta.dirname, "../../../tests/e2e/verification_matrix.yaml");
const matrixRaw = readFileSync(matrixPath, "utf8");
describe("B8 verification matrix (UI contract)", () => {
    it("includes discovery and pipeline scenarios", () => {
        expect(matrixRaw).toContain("discovery_catalogs");
        expect(matrixRaw).toContain("discovery_snapshot");
        expect(matrixRaw).toContain("/api/discovery/catalogs");
        expect(matrixRaw).toContain("/api/plans/analyze");
    });
});
