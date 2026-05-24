/**
 * Validation summary panel. Counts come from the validator's deterministic
 * checks; the per-issue list is rendered below the counts so the user can
 * see which checks fired before approving.
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui";
import { DIFF_LABELS } from "@/constants/dv";
import { PIPELINE_LABELS, type PipelineRun } from "@/constants/pipeline";

const SEVERITY_CLASS: Readonly<Record<string, string>> = Object.freeze({
  error: "text-destructive",
  warning: "text-warning",
  info: "text-info",
});

export function ValidationCard({ run }: { run: PipelineRun }) {
  const report = run.validation;
  if (!report) return null;
  const { summary, issues } = report;

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {PIPELINE_LABELS.sectionValidation}{" "}
          <span className="text-xs font-normal text-muted-foreground">
            ({summary.errors} errors · {summary.warnings} warnings · {summary.infos} infos)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div className="flex gap-4">
          <span className="text-destructive">{DIFF_LABELS.errors} {summary.errors}</span>
          <span className="text-warning">{DIFF_LABELS.warnings} {summary.warnings}</span>
          <span className="text-info">{DIFF_LABELS.infos} {summary.infos}</span>
        </div>
        {issues.length === 0 ? (
          <p className="text-muted-foreground">All checks passed.</p>
        ) : (
          <ul className="ml-5 list-disc space-y-1">
            {issues.map((issue, i) => (
              <li
                key={`${issue.code}-${i}`}
                className={SEVERITY_CLASS[issue.severity] ?? "text-muted-foreground"}
              >
                <span className="font-mono text-xs">[{issue.code}]</span> {issue.message}
                {issue.location && (
                  <span className="ml-1 text-xs text-muted-foreground">@ {issue.location}</span>
                )}
                {issue.suggestion && (
                  <div className="ml-4 text-xs text-muted-foreground">→ {issue.suggestion}</div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
