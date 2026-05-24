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
  useSubmitForReview,
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
