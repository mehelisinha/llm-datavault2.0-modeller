/**
 * Business-vault proposal drilldown: PIT tables, bridge tables, and
 * BV satellites produced by the BvArchitect step. Hidden until the
 * `architect_bv` step finishes.
 */
import { Card, CardContent, CardHeader, CardTitle, Separator } from "@/components/ui";
import { PIPELINE_LABELS, type PipelineRun } from "@/constants/pipeline";

interface Item {
  name: string;
  detail: string;
  rationale?: string;
}

function ItemList({ title, items }: { title: string; items: Item[] }) {
  if (items.length === 0) {
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
        {title} <span className="text-xs font-normal text-muted-foreground">({items.length})</span>
      </h4>
      <ul className="space-y-1.5">
        {items.map((it) => (
          <li key={it.name} className="text-sm">
            <div>
              <span className="font-mono text-xs">{it.name}</span>{" "}
              <span className="text-xs text-muted-foreground">— {it.detail}</span>
            </div>
            {it.rationale && (
              <p className="ml-1 text-xs text-muted-foreground">{it.rationale}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function BvCard({ run }: { run: PipelineRun }) {
  const bv = run.bv;
  if (!bv) return null;

  const pits: Item[] = bv.pit_tables.map((p) => ({
    name: p.name,
    detail: `hub: ${p.parent_hub} · grain: ${p.granularity} · sats: ${p.satellites.join(", ") || "—"}`,
    rationale: p.rationale,
  }));
  const bridges: Item[] = bv.bridge_tables.map((b) => ({
    name: b.name,
    detail: `link: ${b.parent_link} · hubs: ${b.hub_keys.join(", ") || "—"}`,
    rationale: b.rationale,
  }));
  const bvSats: Item[] = bv.bv_satellites.map((s) => ({
    name: s.name,
    detail: `parent: ${s.parent_hub} · computed: ${s.computed_columns.join(", ") || "—"}`,
    rationale: s.rationale,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {PIPELINE_LABELS.sectionBv}{" "}
          <span className="text-xs font-normal text-muted-foreground">
            ({pits.length} PITs · {bridges.length} bridges · {bvSats.length} BV sats)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <ItemList title="PIT tables" items={pits} />
        <Separator />
        <ItemList title="Bridge tables" items={bridges} />
        <Separator />
        <ItemList title="BV satellites" items={bvSats} />
      </CardContent>
    </Card>
  );
}
