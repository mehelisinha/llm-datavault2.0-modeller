/**
 * Diff & validation surface.
 *
 * After Phase B6 this page is intentionally restricted to two actions:
 *
 * 1. **Run schema analyzer** — proposes the modeling plan (hubs / links / sats).
 * 2. **Validate plan**       — produces the ``ValidationReport`` that gates approval.
 *
 * Approval / rejection / request-changes live on the Generate Preview
 * page because they require a server-side DRAFT to exist, which is only
 * created by ``POST /api/plans/{id}/submit-for-review`` from that page.
 * Mixing the controls here led to 409 Conflicts (visible in the API logs)
 * and an unclear workflow.
 */
export default function DiffReviewPage(): import("react/jsx-runtime").JSX.Element;
