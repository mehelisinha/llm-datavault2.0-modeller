/**
 * PipelineRunPage
 * ───────────────
 * Single agentic surface for one pipeline run. Renders all artifacts the
 * orchestrator produces, progressively, so the user can:
 *
 *   1. Watch the step timeline.
 *   2. Acknowledge supervisor risks if the run was paused.
 *   3. Drill into the bronze diff, the modelling plan, and the BV proposal.
 *   4. Review validation issues and the rendered YAML.
 *   5. Submit for review, then approve / reject / request-changes.
 *
 * The page is read-only with respect to the run itself — every mutation
 * goes through the existing API hooks. State sits on the server-side
 * `PipelineRun` record; this component only re-fetches it.
 */
import { useMemo, useState } from "react";
import { useSearch } from "@tanstack/react-router";

import { usePipelineRun, useRunPipeline } from "@/api/hooks";
import { PageShell } from "@/components/PageShell";
import { Spinner } from "@/components/ui";
import {
  PIPELINE_LABELS,
  type PipelineRun,
  type PipelineRunRequest,
} from "@/constants/pipeline";
import { toast } from "@/lib/toast";

import { BvCard } from "./pipeline/BvCard";
import { DiffCard } from "./pipeline/DiffCard";
import { GovernanceCard } from "./pipeline/GovernanceCard";
import { PlanCard } from "./pipeline/PlanCard";
import { RiskCard } from "./pipeline/RiskCard";
import { StatusCard } from "./pipeline/StatusCard";
import { TimelineCard } from "./pipeline/TimelineCard";
import { ValidationCard } from "./pipeline/ValidationCard";
import { YamlCard } from "./pipeline/YamlCard";

const POLL_INTERVAL_MS = 1500;

export default function PipelineRunPage() {
  // Discovery navigates here with the run id and the original request so
  // "Continue anyway" can re-fire the pipeline without re-prompting.
  const search = useSearch({ strict: false }) as {
    runId?: string;
    req?: string;
  };

  const [runId, setRunId] = useState<string | null>(search.runId ?? null);

  const lastRequest = useMemo<PipelineRunRequest | null>(() => {
    if (!search.req) return null;
    try {
      return JSON.parse(decodeURIComponent(search.req)) as PipelineRunRequest;
    } catch {
      return null;
    }
  }, [search.req]);

  const runQuery = usePipelineRun(runId, {
    refetchInterval: ((q: { state: { data?: PipelineRun } }) =>
      q.state.data?.status === "running" ? POLL_INTERVAL_MS : false) as never,
  } as never);

  const rerun = useRunPipeline({
    onSuccess: (run) => {
      setRunId(run.run_id);
      void runQuery.refetch();
    },
    onError: (err) => toast.error("Could not re-run the pipeline", String(err.message)),
  });

  const run = runQuery.data ?? null;

  const handleAcknowledge = () => {
    if (!lastRequest) {
      toast.error("Missing request payload to re-run");
      return;
    }
    rerun.mutate({ ...lastRequest, acknowledge_risks: true });
  };

  return (
    <PageShell
      title={PIPELINE_LABELS.pageTitle}
      description={PIPELINE_LABELS.pageDescription}
    >
      {!runId ? (
        <p className="text-sm text-muted-foreground">{PIPELINE_LABELS.empty}</p>
      ) : runQuery.isPending ? (
        <Spinner className="h-5 w-5" />
      ) : run ? (
        <div className="space-y-4">
          <StatusCard run={run} />
          {run.risk_assessment?.recommendation === "pause" && (
            <RiskCard
              run={run}
              onAcknowledge={handleAcknowledge}
              acknowledging={rerun.isPending}
            />
          )}
          <TimelineCard run={run} />
          <DiffCard run={run} />
          <PlanCard run={run} />
          <BvCard run={run} />
          <ValidationCard run={run} />
          <YamlCard run={run} />
          <GovernanceCard run={run} />
        </div>
      ) : null}
    </PageShell>
  );
}
