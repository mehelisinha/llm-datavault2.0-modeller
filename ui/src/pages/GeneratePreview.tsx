import { useCallback, useEffect, useRef, useState } from "react";

import {
  useApprovePlan,
  useGenerateYaml,
  useRejectPlan,
  useRequestChanges,
  useSubmitForReview,
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
import { GENERATE_LABELS } from "@/constants/routes";
import { usePipeline } from "@/context/DwaPipelineContext";
import { toast } from "@/lib/toast";

// ── Download helper ─────────────────────────────────────────────────────────
// Appends a temporary <a> to the DOM before clicking so all browsers honour
// the download attribute without security restrictions on detached elements.
function downloadTextFile(content: string, filename: string): void {
  const blob = new Blob([content], { type: "text/yaml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  // Revoke slightly later so the browser has time to start the download.
  window.setTimeout(() => URL.revokeObjectURL(url), 200);
}

// ── Scroll helper ────────────────────────────────────────────────────────────
// Finds the nearest scrollable ancestor (not necessarily window) and scrolls
// it so the target element is near the top with an offset for the fixed nav.
const SCROLL_OFFSET_PX = 88; // approximate nav height

function scrollToElement(el: HTMLElement): void {
  // Walk up the DOM to find the first element that actually scrolls.
  let container: Element | null = el.parentElement;
  while (container && container !== document.documentElement) {
    const style = window.getComputedStyle(container);
    const overflowY = style.overflowY;
    if (
      (overflowY === "auto" || overflowY === "scroll") &&
      container.scrollHeight > container.clientHeight
    ) {
      break;
    }
    container = container.parentElement;
  }

  const scrollRoot = container ?? document.documentElement;
  const elTop = el.getBoundingClientRect().top;
  const containerTop = scrollRoot === document.documentElement
    ? 0
    : scrollRoot.getBoundingClientRect().top;
  const targetScroll = scrollRoot.scrollTop + elTop - containerTop - SCROLL_OFFSET_PX;

  scrollRoot.scrollTo({ top: Math.max(0, targetScroll), behavior: "smooth" });
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
  const { plan, bv, system, validation, planId, renderedYaml, setRenderedYaml } = usePipeline();
  const [comment, setComment] = useState("");
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const decisionRef = useRef<HTMLDivElement>(null);

  // ── Scroll after submit ──────────────────────────────────────────────────
  // Stored in a ref so the effect can detect the moment hasSubmitted flips.
  const shouldScrollRef = useRef(false);

  useEffect(() => {
    if (shouldScrollRef.current && decisionRef.current) {
      shouldScrollRef.current = false;
      scrollToElement(decisionRef.current);
    }
  });

  // ── Mutations ──────────────────────────────────────────────────────────
  const generate = useGenerateYaml({
    onSuccess: (data) => {
      const anyData = data as any;
      const yaml: string =
        anyData.monolithic_yaml ||
        (data.files && data.files.length > 0
          ? data.files[0].body
          : (data.files ?? []).map((f) => f.body).join("\n---\n"));
      setRenderedYaml(yaml || "");
      const lineCount = yaml ? yaml.split("\n").length : 0;
      toast.success(
        APPROVAL_LABELS.generateSuccess,
        yaml ? `${lineCount} lines generated` : "No YAML returned — check pipeline steps.",
      );
    },
    onError: (err) => toast.error(APPROVAL_LABELS.generateError, err.message),
  });

  const submit = useSubmitForReview(planId ?? "", {
    onSuccess: () => {
      shouldScrollRef.current = true;
      setHasSubmitted(true); // triggers re-render → useEffect fires → scroll
      toast.success(APPROVAL_LABELS.submitSuccess, `Plan ID: ${planId ?? "—"}`);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.submitError, err.message),
  });

  const approve = useApprovePlan(planId ?? "", {
    onSuccess: () => {
      setComment("");
      toast.success(APPROVAL_LABELS.approveSuccess, `Plan ID: ${planId ?? "—"}`);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.approveError, err.message),
  });

  const reject = useRejectPlan(planId ?? "", {
    onSuccess: () => {
      setComment("");
      toast.success(APPROVAL_LABELS.rejectSuccess, `Plan ID: ${planId ?? "—"}`);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.rejectError, err.message),
  });

  const requestChanges = useRequestChanges(planId ?? "", {
    onSuccess: () => {
      setComment("");
      toast.success(APPROVAL_LABELS.requestChangesSuccess, `Plan ID: ${planId ?? "—"}`);
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
    downloadTextFile(renderedYaml, GENERATE_LABELS.downloadFilename(systemId));
  }, [renderedYaml, system, plan]);

  const handleSubmit = () => {
    if (!plan || !validation || !planId || !renderedYaml) return;
    submit.mutate({ plan, rendered_yaml: renderedYaml, validation });
  };

  const handleApprove = () => {
    if (!planId) return;
    approve.mutate(comment.trim() ? { comment: comment.trim() } : { comment: null });
  };

  const handleReject = () => {
    if (!planId || !comment.trim()) return;
    reject.mutate({ comment: comment.trim() });
  };

  const handleRequestChanges = () => {
    if (!planId || !comment.trim()) return;
    requestChanges.mutate({ comment: comment.trim() });
  };

  // ── Derived state ──────────────────────────────────────────────────────
  const hasYaml = Boolean(renderedYaml && renderedYaml.length > 0);
  const canGenerate = Boolean(plan) && !generate.isPending;
  const canSubmit = Boolean(plan && validation && planId && renderedYaml);
  const validationOk = validation ? validationPassed(validation) : false;
  const canApprove = hasSubmitted && validationOk && Boolean(planId) && !approve.isPending;
  const canReject = hasSubmitted && Boolean(planId) && Boolean(comment.trim()) && !reject.isPending;
  const canRequestChanges =
    hasSubmitted && Boolean(planId) && Boolean(comment.trim()) && !requestChanges.isPending;

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
            onClick={handleSubmit}
            disabled={!canSubmit || submit.isPending}
          >
            {submit.isPending ? <Spinner className="h-4 w-4" /> : null}
            {APPROVAL_LABELS.submitLabel}
          </Button>
        </div>
      }
    >
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
            <p className="text-muted-foreground">{GENERATE_LABELS.noPlanHint}</p>
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
              <p className="text-sm text-muted-foreground">{APPROVAL_LABELS.submitNeeded}</p>
            ) : !validationOk ? (
              <p className="text-sm text-destructive">{APPROVAL_LABELS.validationBlock}</p>
            ) : null}
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
