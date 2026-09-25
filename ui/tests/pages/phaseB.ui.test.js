import { jsx as _jsx } from "react/jsx-runtime";
import { render, screen } from "@testing-library/react";
import DiffReviewPage from "@/pages/DiffReview";
import DiscoveryPage from "@/pages/Discovery";
import GeneratePreviewPage from "@/pages/GeneratePreview";
import HistoryPage from "@/pages/History";
import PlanReviewPage from "@/pages/PlanReview";
import { DIFF_LABELS, PLAN_REVIEW_LABELS } from "@/constants/dv";
import { DISCOVERY_LABELS } from "@/constants/discovery";
import { PIPELINE_LABELS } from "@/constants/pipeline";
import { GENERATE_LABELS, HISTORY_LABELS } from "@/constants/routes";
import { createTestWrapper } from "../test-utils";
describe("Phase B UI pages", () => {
    const Wrapper = createTestWrapper();
    it("renders DiffReviewPage actions", () => {
        render(_jsx(DiffReviewPage, {}), { wrapper: Wrapper });
        expect(screen.getByRole("button", { name: DIFF_LABELS.analyze })).toBeInTheDocument();
        expect(screen.getByText(/discovery snapshot first/i)).toBeInTheDocument();
    });
    it("renders DiscoveryPage with primary Generate Vault action and advanced snapshot", () => {
        render(_jsx(DiscoveryPage, {}), { wrapper: Wrapper });
        expect(screen.getByRole("heading", { name: DISCOVERY_LABELS.pageTitle })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: PIPELINE_LABELS.runButton })).toBeInTheDocument();
        expect(screen.getByLabelText(DISCOVERY_LABELS.catalog)).toBeInTheDocument();
        expect(screen.getByLabelText(DISCOVERY_LABELS.bronzeSchema)).toBeInTheDocument();
        expect(screen.getByLabelText(DISCOVERY_LABELS.vaultSchema)).toBeInTheDocument();
        expect(screen.getByText(DISCOVERY_LABELS.advancedTitle)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: DISCOVERY_LABELS.snapshot })).toBeInTheDocument();
    });
    it("renders GeneratePreviewPage", () => {
        render(_jsx(GeneratePreviewPage, {}), { wrapper: Wrapper });
        expect(screen.getByRole("button", { name: GENERATE_LABELS.button })).toBeInTheDocument();
    });
    it("renders PlanReviewPage", () => {
        render(_jsx(PlanReviewPage, {}), { wrapper: Wrapper });
        expect(screen.getByRole("heading", { name: PLAN_REVIEW_LABELS.pageTitle })).toBeInTheDocument();
    });
    it("renders HistoryPage", () => {
        render(_jsx(HistoryPage, {}), { wrapper: Wrapper });
        expect(screen.getAllByText(HISTORY_LABELS.pageTitle).length).toBeGreaterThan(0);
    });
});
