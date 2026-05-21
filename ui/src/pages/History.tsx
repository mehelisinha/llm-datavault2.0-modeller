import { PageShell } from "@/components/PageShell";
import { Card, CardContent, CardHeader, CardTitle, Separator, Spinner } from "@/components/ui";
import { useHistory } from "@/api/hooks";
import { HISTORY_LABELS } from "@/constants/routes";

export default function HistoryPage() {
  const { data, isPending, error } = useHistory();
  const records = data ?? [];

  return (
    <PageShell
      title={HISTORY_LABELS.pageTitle}
      description={HISTORY_LABELS.pageDescription}
    >
      <Card>
        <CardHeader>
          <CardTitle>Plan History</CardTitle>
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
