/**
 * Bronze-vs-vault change-set drilldown. Mirrors the table the old
 * DiffReview page rendered, with category tabs (new / drift / unchanged
 * / orphaned). Hidden until the snapshot step finishes.
 */
import { useMemo, useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Separator, StatusPill } from "@/components/ui";
import {
  CHANGE_CATEGORY_LABELS,
  CHANGE_CATEGORY_VALUES,
  DIFF_LABELS,
  type ChangeCategory,
} from "@/constants/dv";
import { PIPELINE_LABELS, type PipelineRun } from "@/constants/pipeline";

export function DiffCard({ run }: { run: PipelineRun }) {
  const changeSet = run.change_set;
  const [selectedTab, setSelectedTab] = useState<ChangeCategory>(CHANGE_CATEGORY_VALUES[0]);

  const counts = useMemo(() => {
    const map: Record<ChangeCategory, number> = { new: 0, drift: 0, unchanged: 0, orphaned: 0 };
    for (const c of changeSet?.changes ?? []) map[c.category] += 1;
    return map;
  }, [changeSet]);

  const filtered = useMemo(
    () => (changeSet?.changes ?? []).filter((c) => c.category === selectedTab),
    [changeSet, selectedTab],
  );

  if (!changeSet) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {PIPELINE_LABELS.sectionDiff}{" "}
          <span className="text-xs font-normal text-muted-foreground">
            ({counts.new} new · {counts.drift} drift · {counts.unchanged} unchanged · {counts.orphaned} orphaned)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex flex-wrap gap-2">
          {CHANGE_CATEGORY_VALUES.map((cat) => (
            <Button
              key={cat}
              intent={selectedTab === cat ? "primary" : "secondary"}
              size="sm"
              onClick={() => setSelectedTab(cat)}
            >
              {CHANGE_CATEGORY_LABELS[cat]} ({counts[cat]})
            </Button>
          ))}
        </div>
        <Separator />
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="py-1 pr-4">Table</th>
                <th className="py-1 pr-4">Category</th>
                <th className="py-1 pr-4">Risk</th>
                <th className="py-1">Notes</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-3 text-center text-muted-foreground">
                    {DIFF_LABELS.noChanges}
                  </td>
                </tr>
              ) : (
                filtered.map((change) => (
                  <tr key={change.table_name} className="border-t border-border">
                    <td className="py-1 pr-4 font-mono text-xs">{change.table_name}</td>
                    <td className="py-1 pr-4">
                      <StatusPill category={change.category} />
                    </td>
                    <td className="py-1 pr-4">{change.risk}</td>
                    <td className="py-1 text-muted-foreground">
                      {change.notes?.join("; ") ?? ""}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
