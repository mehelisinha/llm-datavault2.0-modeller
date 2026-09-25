import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle, Icon } from "@/components/ui";
import {
  PIPELINE_STEP_ORDER,
  STEP_AGENT_LABELS,
  STEP_LABELS,
} from "@/constants/pipeline";
import { env } from "@/env";
import { formatDuration } from "@/lib/formatDuration";

const TICK_MS = 200;

/** Live wall-clock since the component mounted, in milliseconds. */
function useElapsed(active: boolean): number {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!active) return;
    const start = performance.now();
    setElapsed(0);
    const id = window.setInterval(() => setElapsed(performance.now() - start), TICK_MS);
    return () => window.clearInterval(id);
  }, [active]);
  return elapsed;
}

interface RunProgressProps {
  /** Number of tables in the run; drives the large-catalog hint. */
  tableCount: number;
  /** Title override (e.g. "Re-running after risk acknowledgement"). */
  title?: string;
}

/**
 * Live multi-agent run progress.
 *
 * The backend run is a single blocking request, so we can't stream the exact
 * step that is currently executing. Instead of a bare button spinner this shows
 * the full agent sequence, an indeterminate progress bar, and a running elapsed
 * timer — honest feedback that the pipeline is working and roughly how long it
 * has taken. Large catalogs get an extra note because batched analysis is slow.
 */
export function RunProgress({ tableCount, title }: RunProgressProps) {
  const elapsed = useElapsed(true);
  const isLargeCatalog = tableCount > env.largeCatalogThreshold;

  return (
    <Card className="animate-fade-in-up border-primary/20 shadow-glow">
      <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="flex items-center gap-2">
          <Icon icon={Loader2} className="animate-spin text-primary" />
          {title ?? "Generating vault"}
        </CardTitle>
        <span
          className="font-mono text-sm tabular-nums text-muted-foreground"
          aria-label="Elapsed time"
        >
          {formatDuration(elapsed)}
        </span>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Indeterminate progress bar */}
        <div
          className="relative h-1.5 w-full overflow-hidden rounded-full bg-secondary"
          role="progressbar"
          aria-label="Pipeline running"
        >
          <div className="absolute inset-y-0 left-0 w-1/4 animate-progress-indeterminate rounded-full bg-gradient-brand" />
        </div>

        <ol className="space-y-2.5">
          {PIPELINE_STEP_ORDER.map((step) => (
            <li key={step} className="flex items-start gap-3 text-sm">
              <span
                className="mt-1.5 h-2 w-2 shrink-0 animate-pulse rounded-full bg-primary"
                aria-hidden
              />
              <span>
                <span className="font-medium text-foreground">{STEP_LABELS[step]}</span>
                <span className="block text-xs text-muted-foreground">
                  {STEP_AGENT_LABELS[step]}
                </span>
              </span>
            </li>
          ))}
        </ol>

        {isLargeCatalog ? (
          <p className="rounded-md border border-info/30 bg-info/10 px-3 py-2 text-xs text-foreground">
            Large catalog ({tableCount} tables, over the {env.largeCatalogThreshold}-table
            threshold) — the modeller analyses tables in parallel batches, so this can take a
            few minutes. You can leave this page open.
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">
            The assistant runs several agents in sequence; this usually takes under a minute.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
