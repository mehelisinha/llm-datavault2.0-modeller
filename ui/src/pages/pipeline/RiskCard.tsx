/**
 * Supervisor risk banner. Shown only when `risk_assessment.recommendation`
 * is "pause"; the user can either review the linked sections below or
 * acknowledge the risk and let the pipeline continue with the same input.
 */
import { Button, Card, CardContent, CardHeader, CardTitle, Spinner } from "@/components/ui";
import { PIPELINE_LABELS, RISK_KIND_LABELS, type PipelineRun } from "@/constants/pipeline";

interface Props {
  run: PipelineRun;
  onAcknowledge: () => void;
  acknowledging: boolean;
}

export function RiskCard({ run, onAcknowledge, acknowledging }: Props) {
  const assessment = run.risk_assessment;
  if (!assessment) return null;
  return (
    <Card className="border-amber-400">
      <CardHeader>
        <CardTitle>{PIPELINE_LABELS.riskBanner}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          {assessment.signals.map((s, idx) => (
            <li key={`${s.kind}-${idx}`}>
              <strong>{RISK_KIND_LABELS[s.kind]}</strong>{" "}
              <span className="text-muted-foreground">({s.severity})</span> — {s.detail}
            </li>
          ))}
        </ul>
        <Button className="mt-4" onClick={onAcknowledge} disabled={acknowledging}>
          {acknowledging ? <Spinner className="h-4 w-4" /> : null}
          {PIPELINE_LABELS.ackButton}
        </Button>
      </CardContent>
    </Card>
  );
}
