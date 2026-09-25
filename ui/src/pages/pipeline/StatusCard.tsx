/**
 * Top-level status card showing the run's lifecycle state and any fatal
 * error returned by the orchestrator.
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui";
import { STATUS_LABELS, type PipelineRun } from "@/constants/pipeline";

export function StatusCard({ run }: { run: PipelineRun }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{STATUS_LABELS[run.status]}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">Run ID: {run.run_id}</p>
        {run.error_detail && (
          <p className="mt-2 text-sm text-destructive">{run.error_detail}</p>
        )}
      </CardContent>
    </Card>
  );
}
