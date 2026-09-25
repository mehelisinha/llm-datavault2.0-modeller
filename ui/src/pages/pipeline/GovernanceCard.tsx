/**
 * Governance gate.
 *
 * Mirrors the workflow that previously lived on `GeneratePreview`: the user
 * must submit the rendered plan for review, then can approve / reject /
 * request-changes. Approval is only enabled when validation passes (zero
 * errors), exactly like the old surface.
 *
 * Plan ID is sourced from `run.plan.system_id` — there is no separate
 * planId on the pipeline-run contract because the orchestrator does not
 * create a draft until "Submit for review" is clicked.
 */
import { useEffect, useRef, useState } from "react";

import {
  useApprovePlan,
  useRejectPlan,
  useRequestChanges,
  useRunRecommendation,
  useSubmitForReview,
  type GovernanceRecommendation,
} from "@/api/hooks";
import { validationPassed } from "@/api/types";
import { Button, Card, CardContent, CardHeader, CardTitle, Separator, Spinner } from "@/components/ui";
import { APPROVAL_LABELS } from "@/constants/dv";
import { PIPELINE_LABELS, type PipelineRun } from "@/constants/pipeline";
import { toast } from "@/lib/toast";

export function GovernanceCard({ run }: { run: PipelineRun }) {
  const [comment, setComment] = useState("");
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  const plan = run.plan;
  const validation = run.validation;
  const yamlContent = run.rendered_yaml ?? "";
  const planId = plan?.system_id ?? null;

  // Only visible when the run is settled.
  const runSettled = run.status === "done" || run.status === "paused";
  const canRender = runSettled && plan && validation && yamlContent;

  // Plain-language approve/review/reject guidance from the backend checks.
  const recQuery = useRunRecommendation(run.run_id, {
    enabled: Boolean(runSettled && plan),
  } as never);
  const rec = recQuery.data ?? null;
  const prefilled = useRef(false);

  const submit = useSubmitForReview({
    onSuccess: () => {
      setHasSubmitted(true);
      toast.success(APPROVAL_LABELS.submitSuccess, `Plan ID: ${planId ?? "—"}`);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.submitError, err.message),
  });

  const approve = useApprovePlan({
    onSuccess: () => {
      setComment("");
      toast.success(APPROVAL_LABELS.approveSuccess, `Plan ID: ${planId ?? "—"}`);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.approveError, err.message),
  });

  const reject = useRejectPlan({
    onSuccess: () => {
      setComment("");
      toast.success(APPROVAL_LABELS.rejectSuccess, `Plan ID: ${planId ?? "—"}`);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.rejectError, err.message),
  });

  const requestChanges = useRequestChanges({
    onSuccess: () => {
      setComment("");
      toast.success(APPROVAL_LABELS.requestChangesSuccess, `Plan ID: ${planId ?? "—"}`);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.requestChangesError, err.message),
  });

  useEffect(() => {
    if (hasSubmitted && cardRef.current) {
      window.requestAnimationFrame(() => {
        cardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }, [hasSubmitted]);

  // Pre-fill the reject comment from the recommendation's reasons the first time
  // it arrives with a REJECT verdict — so a non-expert can reject with a
  // meaningful message without having to write one. Never overwrites typed text.
  useEffect(() => {
    if (rec && rec.verdict === "reject" && !prefilled.current && !comment && rec.rejection_message) {
      setComment(rec.rejection_message);
      prefilled.current = true;
    }
  }, [rec, comment]);

  if (!canRender) return null;

  const validationOk = validationPassed(validation);
  const trimmed = comment.trim();

  const handleSubmit = () => {
    if (!plan || !planId || !yamlContent || !validation) return;
    submit.mutate({
      planId,
      body: { plan, rendered_yaml: yamlContent, validation },
    });
  };

  const handleApprove = () => {
    if (!planId) return;
    approve.mutate({ planId, body: trimmed ? { comment: trimmed } : { comment: null } });
  };

  const handleReject = () => {
    if (!planId || !trimmed) return;
    reject.mutate({ planId, body: { comment: trimmed } });
  };

  const handleRequestChanges = () => {
    if (!planId || !trimmed) return;
    requestChanges.mutate({ planId, body: { comment: trimmed } });
  };

  const canSubmit = !submit.isPending;
  const canApprove = hasSubmitted && validationOk && !approve.isPending;
  const canReject = hasSubmitted && Boolean(trimmed) && !reject.isPending;
  const canRequestChanges = hasSubmitted && Boolean(trimmed) && !requestChanges.isPending;

  return (
    <div ref={cardRef} className="scroll-mt-24">
      <Card className={hasSubmitted ? "shadow-md ring-2 ring-primary/40" : undefined}>
        <CardHeader>
          <CardTitle>{PIPELINE_LABELS.sectionGovernance}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {rec && rec.verdict ? <RecommendationBanner rec={rec} /> : null}
          {!hasSubmitted ? (
            <>
              <p className="text-sm text-muted-foreground">{APPROVAL_LABELS.submitNeeded}</p>
              <Button onClick={handleSubmit} disabled={!canSubmit}>
                {submit.isPending ? <Spinner className="h-4 w-4" /> : null}
                {APPROVAL_LABELS.submitLabel}
              </Button>
            </>
          ) : (
            <>
              {!validationOk && (
                <p className="text-sm text-destructive">{APPROVAL_LABELS.validationBlock}</p>
              )}
              <Separator />
              <label htmlFor="dwa-decision-comment" className="block text-sm font-medium">
                {APPROVAL_LABELS.commentLabel}
              </label>
              <textarea
                id="dwa-decision-comment"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder={APPROVAL_LABELS.commentPlaceholder}
                rows={3}
                className="block w-full rounded border border-input bg-background px-2 py-1 text-sm"
              />
              <div className="flex flex-wrap gap-2">
                <Button onClick={handleApprove} disabled={!canApprove}>
                  {approve.isPending ? <Spinner className="h-4 w-4" /> : null}
                  {APPROVAL_LABELS.approve}
                </Button>
                <Button
                  intent="destructive"
                  onClick={handleReject}
                  disabled={!canReject}
                  title={!trimmed ? "Comment required" : undefined}
                >
                  {reject.isPending ? <Spinner className="h-4 w-4" /> : null}
                  {APPROVAL_LABELS.reject}
                </Button>
                <Button
                  intent="outline"
                  onClick={handleRequestChanges}
                  disabled={!canRequestChanges}
                  title={!trimmed ? "Comment required" : undefined}
                >
                  {requestChanges.isPending ? <Spinner className="h-4 w-4" /> : null}
                  {APPROVAL_LABELS.requestChanges}
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const VERDICT_STYLES: Record<string, { box: string; label: string }> = {
  approve: {
    box: "border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100",
    label: "Recommendation: APPROVE",
  },
  review: {
    box: "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100",
    label: "Recommendation: REVIEW",
  },
  reject: {
    box: "border-destructive/40 bg-destructive/10 text-destructive",
    label: "Recommendation: REJECT",
  },
};

/**
 * Plain-language guidance so a non-expert knows whether to approve. It never
 * decides — the buttons still do — it only summarises the objective checks
 * (source grounding, DV2 conformance, gold match) into a verdict + reasons.
 */
function RecommendationBanner({ rec }: { rec: GovernanceRecommendation }) {
  const style = VERDICT_STYLES[rec.verdict] ?? VERDICT_STYLES.review;
  const reasons = [
    ...rec.blocking_reasons.map((r) => ({ key: `b:${r}`, mark: "⛔", text: r })),
    ...rec.review_reasons.map((r) => ({ key: `r:${r}`, mark: "•", text: r })),
  ];
  return (
    <div className={`rounded-md border p-3 text-sm ${style.box}`}>
      <p className="font-semibold">{style.label}</p>
      {reasons.length > 0 ? (
        <ul className="mt-1 space-y-0.5">
          {reasons.map((r) => (
            <li key={r.key}>
              {r.mark} {r.text}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1">Nothing was flagged — safe to approve.</p>
      )}
    </div>
  );
}
