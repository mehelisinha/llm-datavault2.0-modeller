import { useMemo, useState } from "react";

import { useAnalyzePlan, useValidatePlan } from "@/api/hooks";
import type { TableChange } from "@/api/types";
import { PageShell } from "@/components/PageShell";
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Separator,
  Spinner,
  StatusPill,
} from "@/components/ui";
import {
  APPROVAL_LABELS,
  CHANGE_CATEGORY_LABELS,
  CHANGE_CATEGORY_VALUES,
  DIFF_LABELS,
  type ChangeCategory,
} from "@/constants/dv";
import { usePipeline } from "@/context/DwaPipelineContext";
import { toast } from "@/lib/toast";

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
export default function DiffReviewPage() {
  const {
    system,
    bronzeSnapshot,
    changeSet,
    plan,
    validation,
    setPlan,
    setValidation,
  } = usePipeline();
  const [selectedTab, setSelectedTab] = useState<ChangeCategory>(CHANGE_CATEGORY_VALUES[0]);

  const analyze = useAnalyzePlan({
    onSuccess: (data) => {
      setPlan(data);
      toast.success(APPROVAL_LABELS.analyzeSuccess);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.analyzeError, err.message),
  });
  const validate = useValidatePlan({
    onSuccess: (data) => {
      setValidation(data);
      toast.success(APPROVAL_LABELS.validateSuccess, `Errors: ${data.summary.errors} · Warnings: ${data.summary.warnings}`);
    },
    onError: (err) => toast.error(APPROVAL_LABELS.validateError, err.message),
  });

  const changes = changeSet?.changes ?? [];
  const filteredDiff = useMemo(
    () => changes.filter((c) => c.category === selectedTab),
    [changes, selectedTab],
  );

  const canAnalyze = Boolean(system && bronzeSnapshot && changeSet);
  const canValidate = Boolean(plan);

  const runAnalyze = () => {
    if (!system || !bronzeSnapshot || !changeSet) return;
    analyze.mutate({ system, bronze: bronzeSnapshot, change_set: changeSet });
  };

  const runValidate = () => {
    if (!plan) return;
    validate.mutate({ plan });
  };

  return (
    <PageShell
      title={DIFF_LABELS.pageTitle}
      description={DIFF_LABELS.pageDescription}
      actions={
        <div className="flex flex-wrap gap-2">
          <Button onClick={runAnalyze} disabled={!canAnalyze || analyze.isPending}>
            {analyze.isPending ? <Spinner className="h-4 w-4" /> : null}
            {DIFF_LABELS.analyze}
          </Button>
          <Button intent="secondary" onClick={runValidate} disabled={!canValidate || validate.isPending}>
            {validate.isPending ? <Spinner className="h-4 w-4" /> : null}
            {DIFF_LABELS.validate}
          </Button>
        </div>
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>{DIFF_LABELS.pageTitle}</CardTitle>
        </CardHeader>
        <CardContent>
          {!changeSet ? (
            <p className="text-muted-foreground">Run a discovery snapshot first.</p>
          ) : (
            <>
              <div className="mb-4 flex flex-wrap gap-2">
                {CHANGE_CATEGORY_VALUES.map((cat) => (
                  <Button
                    key={cat}
                    intent={selectedTab === cat ? "primary" : "secondary"}
                    size="sm"
                    onClick={() => setSelectedTab(cat)}
                  >
                    {CHANGE_CATEGORY_LABELS[cat]}
                  </Button>
                ))}
              </div>
              <Separator />
              {analyze.isPending ? (
                <div className="flex justify-center py-8">
                  <Spinner />
                </div>
              ) : analyze.error ? (
                <p className="py-4 text-destructive">
                  {analyze.error instanceof Error
                    ? analyze.error.message
                    : String(analyze.error)}
                </p>
              ) : (
                <div className="mt-4 overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr>
                        <th className="text-left">Table</th>
                        <th className="text-left">Category</th>
                        <th className="text-left">Risk</th>
                        <th className="text-left">Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDiff.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="text-center text-muted-foreground">
                            {DIFF_LABELS.noChanges}
                          </td>
                        </tr>
                      ) : (
                        filteredDiff.map((change: TableChange) => (
                          <tr key={change.table_name}>
                            <td>{change.table_name}</td>
                            <td>
                              <StatusPill category={change.category} />
                            </td>
                            <td>{change.risk}</td>
                            <td>{change.notes?.join("; ") ?? ""}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}
              {validation ? (
                <div className="mt-6 space-y-2">
                  <div className="font-semibold">{DIFF_LABELS.validationSummary}</div>
                  <div className="flex gap-4">
                    <span className="text-destructive">
                      {DIFF_LABELS.errors} {validation.summary.errors}
                    </span>
                    <span className="text-warning">
                      {DIFF_LABELS.warnings} {validation.summary.warnings}
                    </span>
                    <span className="text-info">
                      {DIFF_LABELS.infos} {validation.summary.infos}
                    </span>
                  </div>
                  <ul className="ml-6 list-disc">
                    {validation.issues.map((issue, i) => (
                      <li
                        key={`${issue.code}-${i}`}
                        className={
                          issue.severity === "error"
                            ? "text-destructive"
                            : issue.severity === "warning"
                              ? "text-warning"
                              : "text-info"
                        }
                      >
                        {issue.message}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}
