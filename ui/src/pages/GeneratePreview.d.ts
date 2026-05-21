/**
 * Generate Preview page.
 *
 * Owns the **end of the pipeline**:
 *
 * 1. *Generate YAML Preview* — calls ``POST /api/plans/generate`` and shows
 *    the deterministic per-object files.
 * 2. *Submit for review*     — creates the server-side ``DRAFT`` row that
 *    the approval gate requires. Until this succeeds there is no plan in
 *    the audit store and the approval endpoints would return 409.
 * 3. *Approve / Reject / Request changes* — only enabled once *Submit for
 *    review* has succeeded. Approval additionally requires
 *    ``validation.passed`` (zero ERRORs), matching the server-side gate.
 *
 * Every mutation surfaces a toast on success and on failure so the user
 * gets immediate feedback regardless of network latency.
 */
export default function GeneratePreviewPage(): import("react/jsx-runtime").JSX.Element;
