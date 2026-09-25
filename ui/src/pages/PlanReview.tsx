import { Link } from "@tanstack/react-router";

import { useArchitectBv } from "@/api/hooks";
import { PageShell } from "@/components/PageShell";
import { Button, Card, CardContent, CardHeader, CardTitle, Separator, Spinner } from "@/components/ui";
import { PLAN_REVIEW_LABELS } from "@/constants/dv";
import { ROUTES, WORKFLOW_LABELS } from "@/constants/routes";
import { usePipeline } from "@/context/DwaPipelineContext";

export default function PlanReviewPage() {
  const { plan, bv, setBv } = usePipeline();
  const architect = useArchitectBv({ onSuccess: (data) => setBv(data) });

  const runArchitect = () => {
    if (!plan) return;
    architect.mutate(plan);
  };

  return (
    <PageShell
      title={PLAN_REVIEW_LABELS.pageTitle}
      description={PLAN_REVIEW_LABELS.pageDescription}
      actions={
        <Button onClick={runArchitect} disabled={!plan || architect.isPending}>
          {PLAN_REVIEW_LABELS.runArchitect}
        </Button>
      }
    >
      <p className="mb-4 text-sm text-muted-foreground">
        {WORKFLOW_LABELS.planWorkflowHint}{" "}
        <Link to={ROUTES.discovery} className="text-primary hover:underline">
          {WORKFLOW_LABELS.backToGenerateVault}
        </Link>
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Modeling plan</CardTitle>
        </CardHeader>
        <CardContent>
          {!plan ? (
            <p className="text-muted-foreground">
              {PLAN_REVIEW_LABELS.empty}{" "}
              <Link to={ROUTES.diff} className="text-primary hover:underline">
                Go to Diff
              </Link>
            </p>
          ) : architect.isPending ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : (
            <div className="space-y-6">
              <section>
                <h3 className="mb-2 font-semibold">Hubs ({plan.hubs?.length ?? 0})</h3>
                <ul className="list-disc pl-6 text-sm">
                  {(plan.hubs ?? []).map((hub: { name: string; source_table: string }) => (
                    <li key={hub.name}>
                      {hub.name} ← {hub.source_table}
                    </li>
                  ))}
                </ul>
              </section>
              <Separator />
              {bv ? (
                <section>
                  <h3 className="mb-2 font-semibold">BV proposal</h3>
                  <p className="text-sm text-muted-foreground">
                    PIT tables: {bv.pit_tables?.length ?? 0} · Bridges:{" "}
                    {bv.bridge_tables?.length ?? 0}
                  </p>
                  <pre className="mt-2 max-h-96 overflow-auto rounded bg-muted p-4 text-xs">
                    {JSON.stringify(bv, null, 2)}
                  </pre>
                </section>
              ) : architect.error ? (
                <p className="text-destructive">
                  {architect.error instanceof Error
                    ? architect.error.message
                    : String(architect.error)}
                </p>
              ) : (
                <p className="text-muted-foreground">{PLAN_REVIEW_LABELS.runArchitect}</p>
              )}
              <div className="mt-6 border-t border-border pt-4">
                <Link to={ROUTES.generatePreview}>
                  <Button>{WORKFLOW_LABELS.continueToGenerateYaml}</Button>
                </Link>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}
