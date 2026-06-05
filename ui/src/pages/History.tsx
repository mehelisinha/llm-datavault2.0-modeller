import { useState } from "react";

import { PageShell } from "@/components/PageShell";
import { Button, Card, CardContent, CardHeader, CardTitle, Separator, Spinner } from "@/components/ui";
import { useHistory, useMe } from "@/api/hooks";
import { HISTORY_LABELS } from "@/constants/routes";
import { cn } from "@/lib/cn";

type Scope = "mine" | "all";

export default function HistoryPage() {
  const me = useMe();
  const isAdmin = me.data?.is_admin ?? false;
  const [scope, setScope] = useState<Scope>("mine");
  const effectiveScope: Scope = isAdmin ? scope : "mine";
  const { data, isPending, error } = useHistory(effectiveScope);
  const records = data ?? [];

  return (
    <PageShell
      title={HISTORY_LABELS.pageTitle}
      description={HISTORY_LABELS.pageDescription}
      actions={
        isAdmin ? (
          <div
            role="group"
            aria-label="History scope"
            className="inline-flex rounded-md border border-border p-0.5"
          >
            {(["mine", "all"] as const).map((value) => (
              <Button
                key={value}
                size="sm"
                intent={effectiveScope === value ? "primary" : "ghost"}
                onClick={() => setScope(value)}
                className={cn("min-w-[7rem]")}
              >
                {value === "mine"
                  ? HISTORY_LABELS.scopeMineLabel
                  : HISTORY_LABELS.scopeAllLabel}
              </Button>
            ))}
          </div>
        ) : null
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>
            {effectiveScope === "all"
              ? HISTORY_LABELS.scopeAllLabel
              : HISTORY_LABELS.scopeMineLabel}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Separator className="mb-4" />
          {isPending ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : error ? (
            <div className="text-destructive">{String(error)}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr>
                    <th className="text-left">Plan ID</th>
                    <th className="text-left">Version</th>
                    <th className="text-left">Status</th>
                    <th className="text-left">Actor</th>
                    <th className="text-left">Timestamp</th>
                    <th className="text-left">Comment</th>
                  </tr>
                </thead>
                <tbody>
                  {records.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="text-center text-muted-foreground">
                        {HISTORY_LABELS.noRecords}
                      </td>
                    </tr>
                  ) : (
                    records.map((rec) => (
                      <tr key={`${rec.plan_id}-${rec.version}`}>
                        <td>{rec.plan_id}</td>
                        <td>{rec.version}</td>
                        <td>{rec.status}</td>
                        <td>{rec.actor}</td>
                        <td>{rec.timestamp}</td>
                        <td>{rec.comment ?? ""}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}
