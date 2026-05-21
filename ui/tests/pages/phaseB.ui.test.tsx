import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-router")>(
    "@tanstack/react-router",
  );
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

import DiffReviewPage from "@/pages/DiffReview";
import DiscoveryPage from "@/pages/Discovery";
import GeneratePreviewPage from "@/pages/GeneratePreview";
import HistoryPage from "@/pages/History";
import PlanReviewPage from "@/pages/PlanReview";
import { DIFF_LABELS, PLAN_REVIEW_LABELS } from "@/constants/dv";
import { DISCOVERY_LABELS } from "@/constants/discovery";
import { GENERATE_LABELS, HISTORY_LABELS } from "@/constants/routes";
import { createTestWrapper } from "../test-utils";

describe("Phase B UI pages", () => {
  const Wrapper = createTestWrapper();

  it("renders DiffReviewPage actions", () => {
    render(<DiffReviewPage />, { wrapper: Wrapper });
    expect(screen.getByRole("button", { name: DIFF_LABELS.analyze })).toBeInTheDocument();
    expect(screen.getByText(/discovery snapshot first/i)).toBeInTheDocument();
  });

  it("renders DiscoveryPage with catalog and schema fields", () => {
    render(<DiscoveryPage />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: DISCOVERY_LABELS.pageTitle })).toBeInTheDocument();
    expect(screen.getByLabelText(DISCOVERY_LABELS.catalog)).toBeInTheDocument();
    expect(screen.getByLabelText(DISCOVERY_LABELS.bronzeSchema)).toBeInTheDocument();
    expect(screen.getByLabelText(DISCOVERY_LABELS.vaultSchema)).toBeInTheDocument();
  });

  it("renders GeneratePreviewPage", () => {
    render(<GeneratePreviewPage />, { wrapper: Wrapper });
    expect(screen.getByRole("button", { name: GENERATE_LABELS.button })).toBeInTheDocument();
  });

  it("renders PlanReviewPage", () => {
    render(<PlanReviewPage />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: PLAN_REVIEW_LABELS.pageTitle })).toBeInTheDocument();
  });

  it("renders HistoryPage", () => {
    render(<HistoryPage />, { wrapper: Wrapper });
    expect(screen.getAllByText(HISTORY_LABELS.pageTitle).length).toBeGreaterThan(0);
  });
});
