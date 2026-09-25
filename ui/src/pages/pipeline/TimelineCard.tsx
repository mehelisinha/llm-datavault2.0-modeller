/**
 * Per-step execution timeline rendered from `PipelineRun.steps`.
 *
 * The orchestrator appends one `PipelineStepResult` per logical step as the
 * run progresses, so this card grows incrementally as the user watches.
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui";
import { PIPELINE_LABELS, STEP_LABELS, type PipelineRun } from "@/constants/pipeline";
import { formatDuration } from "@/lib/formatDuration";

export function TimelineCard({ run }: { run: PipelineRun }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{PIPELINE_LABELS.sectionTimeline}</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-2">
          {run.steps.map((step, idx) => (
            <li key={`${step.step}-${idx}`} className="flex items-center gap-3 text-sm">
              <span
                className={
                  step.status === "ok"
                    ? "text-emerald-600"
                    : step.status === "failed"
                      ? "text-destructive"
                      : "text-muted-foreground"
                }
                aria-hidden
              >
                {step.status === "ok" ? "✓" : step.status === "failed" ? "✕" : "·"}
              </span>
              <span className="font-medium">{STEP_LABELS[step.step]}</span>
              <span className="text-muted-foreground">({formatDuration(step.duration_ms)})</span>
              {step.error && <span className="text-destructive">{step.error}</span>}
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
