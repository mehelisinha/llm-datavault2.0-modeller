/**
 * Modelling-plan drilldown: shows the hubs, links, and satellites the
 * SchemaAnalyzer produced, along with each decision's self-reported
 * confidence and rationale. Hidden until the `analyze` step finishes.
 */
import { Badge, Card, CardContent, CardHeader, CardTitle, Separator } from "@/components/ui";
import type { BadgeIntent } from "@/components/ui";
import { PIPELINE_LABELS, type PipelineRun } from "@/constants/pipeline";

const CONFIDENCE_INTENT: Readonly<Record<string, BadgeIntent>> = Object.freeze({
  high: "success",
  medium: "warning",
  low: "destructive",
});

function ConfidenceBadge({ confidence }: { confidence: string }) {
  return (
    <Badge intent={CONFIDENCE_INTENT[confidence] ?? "neutral"}>{confidence}</Badge>
  );
}

interface DecisionRow {
  name: string;
  source: string;
  confidence: string;
  rationale: string;
  extra?: string;
}

function DecisionList({ title, rows }: { title: string; rows: DecisionRow[] }) {
  if (rows.length === 0) {
    return (
      <section>
        <h4 className="text-sm font-semibold">{title}</h4>
        <p className="text-xs text-muted-foreground">No {title.toLowerCase()} proposed.</p>
      </section>
    );
  }
  return (
    <section>
      <h4 className="mb-2 text-sm font-semibold">
        {title} <span className="text-xs font-normal text-muted-foreground">({rows.length})</span>
      </h4>
      <ul className="space-y-1.5">
        {rows.map((row) => (
          <li key={row.name} className="text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs">{row.name}</span>
              <ConfidenceBadge confidence={row.confidence} />
              <span className="text-xs text-muted-foreground">← {row.source}</span>
              {row.extra && <span className="text-xs text-muted-foreground">· {row.extra}</span>}
            </div>
            {row.rationale && (
              <p className="ml-1 text-xs text-muted-foreground">{row.rationale}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function PlanCard({ run }: { run: PipelineRun }) {
  const plan = run.plan;
  if (!plan) return null;

  const hubs: DecisionRow[] = plan.hubs.map((h) => ({
    name: h.name,
    source: h.source_table,
    confidence: h.confidence,
    rationale: h.rationale,
    extra: `keys: ${h.business_keys.join(", ")}`,
  }));
  const links: DecisionRow[] = plan.links.map((l) => ({
    name: l.name,
    source: l.source_table,
    confidence: l.confidence,
    rationale: l.rationale,
    extra: `fks: ${l.fk_columns.join(", ")}`,
  }));
  const sats: DecisionRow[] = plan.satellites.map((s) => ({
    name: s.name,
    source: s.source_table,
    confidence: s.confidence,
    rationale: s.rationale,
    extra: `parent: ${s.parent_hub}`,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {PIPELINE_LABELS.sectionPlan}{" "}
          <span className="text-xs font-normal text-muted-foreground">
            ({hubs.length} hubs · {links.length} links · {sats.length} sats)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <DecisionList title="Hubs" rows={hubs} />
        <Separator />
        <DecisionList title="Links" rows={links} />
        <Separator />
        <DecisionList title="Satellites" rows={sats} />
      </CardContent>
    </Card>
  );
}
