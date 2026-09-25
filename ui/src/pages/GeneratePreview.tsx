import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";

import {
  useApprovePlan,
  useGenerateYaml,
  useRejectPlan,
  useRequestChanges,
  useSubmitForReview,
  useValidatePlan,
} from "@/api/hooks";
import { validationPassed } from "@/api/types";
import { PageShell } from "@/components/PageShell";
import {
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  Separator,
  Spinner,
} from "@/components/ui";
import { APPROVAL_LABELS } from "@/constants/dv";
import { GENERATE_LABELS, ROUTES, WORKFLOW_LABELS } from "@/constants/routes";
import { usePipeline } from "@/context/DwaPipelineContext";
import { downloadTextFile, YAML_MIME } from "@/lib/download";
import { toast } from "@/lib/toast";

function scrollToElement(el: HTMLElement): void {
  // scroll-mt-24 on the target offsets for the fixed nav header.
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

/**
 * Generate Preview page.
 *
 * 1. **Generate YAML Preview** — POST /api/plans/generate → renders v3 YAML.
 * 2. **Download YAML** — saves the YAML file to disk.
 * 3. **Submit for review** — creates the server-side DRAFT; scrolls to Decision.
 * 4. **Approve / Reject / Request changes** — governance gate.
 */
export default function GeneratePreviewPage() {
  const {
    plan,
    bv,
    system,
    validation,
    planId,
    renderedYaml,
    setRenderedYaml,
    setValidation,
  } = usePipeline();
  const [comment, setComment] = useState("");
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const decisionRef = useRef<HTMLDivElement>(null);

  const effectivePlanId = planId ?? plan?.system_id ?? null;

  useEffect(() => {
    if (hasSubmitted && decisionRef.current) {
      window.requestAnimationFrame(() => {
        if (decisionRef.current) {
          scrollToElement(decisionRef.current);
        }
      });
    }
  }, [hasSubmitted]);

  const validatePlan = useValidatePlan({
    onSuccess: (data) => setValidation(data),
  });

  // ── Mutations ──────────────────────────────────────────────────────────
  const generate = useGenerateYaml({
    onSuccess: (data) => {
      const yaml: string =
        data.monolithic_yaml ||
        (data.files && data.files.length > 0
          ? data.files[0].body
          : (data.files ?? []).map((f) => f.body).join("\n---\n"));
      setRenderedYaml(yaml || "");
      const lineCount = yaml ? yaml.split("\n").length : 0;
      toast.success(
        APPROVAL_LABELS.generateSuccess,
        yaml ? `${lineCount} lines generated` : "No YAML returned — check pipeline steps.",
      );
      if (plan && yaml) {
        validatePlan.mutate({ plan, rendered_yaml: yaml });
      }
    },
    onError: (err) => toast.error(APPROVAL_LABELS.generateError, err.message),
  });

  const submit = useSubmitForReview({
    onSuccess: () => {
      setHasSubmitted(true);
      toast.success(APPROVAL_LABELS.submitSuccess, `Plan ID: ${effectivePlanId ?? "—"}`);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.submitError, err.message),
  });

  const approve = useApprovePlan({
    onSuccess: () => {
      setComment("");
      toast.success(APPROVAL_LABELS.approveSuccess, `Plan ID: ${effectivePlanId ?? "—"}`);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.approveError, err.message),
  });

  const reject = useRejectPlan({
    onSuccess: () => {
      setComment("");
      toast.success(APPROVAL_LABELS.rejectSuccess, `Plan ID: ${effectivePlanId ?? "—"}`);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.rejectError, err.message),
  });

  const requestChanges = useRequestChanges({
    onSuccess: () => {
      setComment("");
      toast.success(
        APPROVAL_LABELS.requestChangesSuccess,
        `Plan ID: ${effectivePlanId ?? "—"}`,
      );
    },
    onError: (err) => toast.error(APPROVAL_LABELS.requestChangesError, err.message),
  });

  // ── Handlers ──────────────────────────────────────────────────────────
  const handlePreview = () => {
    if (!plan) return;
    generate.mutate({ plan, bv: bv ?? null, system, format: "metadata_v3" } as any);
  };

  const handleDownload = useCallback(() => {
    if (!renderedYaml) return;
    const systemId = system?.system_id ?? plan?.system_id ?? "metadata";
    downloadTextFile(renderedYaml, GENERATE_LABELS.downloadFilename(systemId), YAML_MIME);
  }, [renderedYaml, system, plan]);

  const handleSubmit = async () => {
    if (!plan || !renderedYaml || !effectivePlanId) return;
    try {
      let report = validation;
      if (!report) {
        report = await validatePlan.mutateAsync({ plan, rendered_yaml: renderedYaml });
        setValidation(report);
      }
      await submit.mutateAsync({
        planId: effectivePlanId,
        body: { plan, rendered_yaml: renderedYaml, validation: report },
      });
    } catch {
      // Errors surfaced via mutation onError / toast
    }
  };

  const handleApprove = () => {
    if (!effectivePlanId) return;
    approve.mutate({
      planId: effectivePlanId,
      body: comment.trim() ? { comment: comment.trim() } : { comment: null },
    });
  };

  const handleReject = () => {
    if (!effectivePlanId || !comment.trim()) return;
    reject.mutate({ planId: effectivePlanId, body: { comment: comment.trim() } });
  };

  const handleRequestChanges = () => {
    if (!effectivePlanId || !comment.trim()) return;
    requestChanges.mutate({ planId: effectivePlanId, body: { comment: comment.trim() } });
  };

  // ── Derived state ──────────────────────────────────────────────────────
  const hasYaml = Boolean(renderedYaml && renderedYaml.length > 0);
  const canGenerate = Boolean(plan) && !generate.isPending;
  const canSubmit =
    Boolean(plan && renderedYaml && effectivePlanId) &&
    !submit.isPending &&
    !validatePlan.isPending;
  const validationOk = validation ? validationPassed(validation) : false;
  const canApprove =
    hasSubmitted && validationOk && Boolean(effectivePlanId) && !approve.isPending;
  const canReject =
    hasSubmitted && Boolean(effectivePlanId) && Boolean(comment.trim()) && !reject.isPending;
  const canRequestChanges =
    hasSubmitted && Boolean(effectivePlanId) && Boolean(comment.trim()) && !requestChanges.isPending;

  const submitBlockReason = (() => {
    if (!plan) return GENERATE_LABELS.noPlanHint;
    if (!hasYaml) return GENERATE_LABELS.empty;
    if (!effectivePlanId) return "Plan ID is missing — run the schema analyzer on Diff first.";
    return null;
  })();

  return (
    <PageShell
      title={GENERATE_LABELS.pageTitle}
      description={GENERATE_LABELS.pageDescription}
      actions={
        <div className="flex flex-wrap gap-2">
          <Button onClick={handlePreview} disabled={!canGenerate}>
            {generate.isPending ? <Spinner className="h-4 w-4" /> : null}
            {GENERATE_LABELS.button}
          </Button>
          <Button
            intent="secondary"
            onClick={handleDownload}
            disabled={!hasYaml}
            title={hasYaml ? GENERATE_LABELS.download : GENERATE_LABELS.downloadDisabledHint}
          >
            {GENERATE_LABELS.download}
          </Button>
          <Button
            intent="secondary"
            onClick={() => void handleSubmit()}
            disabled={!canSubmit}
            title={submitBlockReason ?? undefined}
          >
            {submit.isPending || validatePlan.isPending ? (
              <Spinner className="h-4 w-4" />
            ) : null}
            {APPROVAL_LABELS.submitLabel}
          </Button>
        </div>
      }
    >
      <p className="mb-4 text-sm text-muted-foreground">
        {WORKFLOW_LABELS.generateWorkflowHint}{" "}
        <Link to={ROUTES.discovery} className="text-primary hover:underline">
          {WORKFLOW_LABELS.backToGenerateVault}
        </Link>
        {" · "}
        <Link to={ROUTES.diff} className="text-primary hover:underline">
          Diff
        </Link>
      </p>

      {/* ── YAML preview ─────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>{GENERATE_LABELS.previewCardTitle}</CardTitle>
        </CardHeader>
        <CardContent>
          <Separator className="mb-4" />
          {plan && !system ? (
            <p className="mb-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700">
              {GENERATE_LABELS.noSystemWarning}
            </p>
          ) : null}
          {!plan ? (
            <p className="text-muted-foreground">
              {GENERATE_LABELS.noPlanHint}{" "}
              <Link to={ROUTES.diff} className="text-primary hover:underline">
                Go to Diff
              </Link>
            </p>
          ) : generate.isPending ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : generate.isError ? (
            <p className="text-destructive">
              {APPROVAL_LABELS.generateError}
              {generate.error ? `: ${generate.error.message}` : ""}
            </p>
          ) : hasYaml ? (
            <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-muted p-4 text-xs leading-relaxed">
              {renderedYaml}
            </pre>
          ) : (
            <p className="text-muted-foreground">{GENERATE_LABELS.empty}</p>
          )}
        </CardContent>
        {hasYaml && (
          <CardFooter className="justify-end border-t pt-4">
            <Button onClick={handleDownload}>{GENERATE_LABELS.download}</Button>
          </CardFooter>
        )}
      </Card>

      {/* ── Governance ───────────────────────────────────────────────── */}
      <div ref={decisionRef} className="mt-6 scroll-mt-24">
        <Card
          className={`transition-all duration-300 ${
            hasSubmitted ? "ring-2 ring-primary/40 shadow-md" : ""
          }`}
        >
          <CardHeader>
            <CardTitle>{APPROVAL_LABELS.section}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!hasSubmitted ? (
              <p className="text-sm text-muted-foreground">
                {submitBlockReason ?? APPROVAL_LABELS.submitNeeded}
              </p>
            ) : !validationOk ? (
              <p className="text-sm text-destructive">
                {APPROVAL_LABELS.validationBlock}
                {validation
                  ? ` (${validation.summary.errors} error(s) — fix on the Diff page or regenerate.)`
                  : null}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">
                Plan submitted. Approve when ready, or reject / request changes with a comment.
              </p>
            )}
            <label className="block text-sm">
              {APPROVAL_LABELS.commentLabel}
              <input
                type="text"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                className="mt-1 block w-full rounded border border-input bg-background px-2 py-1"
                placeholder={APPROVAL_LABELS.commentPlaceholder}
              />
            </label>
          </CardContent>
          <CardFooter className="flex flex-wrap gap-2">
            <Button onClick={handleApprove} disabled={!canApprove}>
              {approve.isPending ? <Spinner className="h-4 w-4" /> : null}
              {APPROVAL_LABELS.approve}
            </Button>
            <Button intent="destructive" onClick={handleReject} disabled={!canReject}>
              {reject.isPending ? <Spinner className="h-4 w-4" /> : null}
              {APPROVAL_LABELS.reject}
            </Button>
            <Button intent="secondary" onClick={handleRequestChanges} disabled={!canRequestChanges}>
              {requestChanges.isPending ? <Spinner className="h-4 w-4" /> : null}
              {APPROVAL_LABELS.requestChanges}
            </Button>
          </CardFooter>
        </Card>
      </div>
    </PageShell>
  );
}
