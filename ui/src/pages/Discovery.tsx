import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";

import { useCatalogs, useDiscoverySnapshot, useRunPipeline, useSchemas, useSchemaTables } from "@/api/hooks";
import { PageShell } from "@/components/PageShell";
import { Button, Card, CardContent, CardHeader, CardTitle, Spinner } from "@/components/ui";
import { DISCOVERY_LABELS } from "@/constants/discovery";
import { PIPELINE_LABELS } from "@/constants/pipeline";
import { ROUTES, WORKFLOW_LABELS } from "@/constants/routes";
import { usePipeline } from "@/context/DwaPipelineContext";
import { env } from "@/env";
import { toast } from "@/lib/toast";

// ── Vault schema hints for auto-selection ──────────────────────────────────
const VAULT_SCHEMA_HINTS = ["raw_vault", "vault"] as const;

// ── Small reusable field wrapper ───────────────────────────────────────────
function FieldRow({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="block text-sm font-medium">
        {label}
      </label>
      {children}
    </div>
  );
}

export default function DiscoveryPage() {
  const navigate = useNavigate();
  const { setSnapshot } = usePipeline();

  const [catalog, setCatalog] = useState<string>(env.defaults.catalog ?? "");
  const [bronzeSchema, setBronzeSchema] = useState<string>(env.defaults.bronzeSchema ?? "");
  const [vaultSchema, setVaultSchema] = useState<string>(env.defaults.vaultSchema ?? "");
  const [selectedTables, setSelectedTables] = useState<Set<string>>(new Set());

  // ── Remote data ──────────────────────────────────────────────────────────
  const { data: catalogData, isPending: catalogsLoading, error: catalogsError } = useCatalogs();
  const { data: schemaData, isPending: schemasLoading, error: schemasError } = useSchemas(
    catalog || null,
  );
  const {
    data: tableData,
    isPending: tablesLoading,
  } = useSchemaTables(catalog || null, bronzeSchema || null);

  const catalogs = useMemo(() => catalogData?.catalogs ?? [], [catalogData]);
  const schemas = useMemo(() => schemaData?.schemas ?? [], [schemaData]);
  const availableTables = useMemo(() => tableData?.tables ?? [], [tableData]);

  const snapshot = useDiscoverySnapshot({
    onSuccess: (data) => {
      setSnapshot(data);
      toast.success(DISCOVERY_LABELS.snapshotSuccess);
      void navigate({ to: ROUTES.diff });
    },
    onError: (err) => toast.error(DISCOVERY_LABELS.snapshotError, String(err.message)),
  });

  // ── Derived state ────────────────────────────────────────────────────────
  const allSelected =
    availableTables.length > 0 && availableTables.every((t) => selectedTables.has(t));

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleCatalogChange = (value: string) => {
    setCatalog(value);
    setBronzeSchema("");
    setVaultSchema("");
    setSelectedTables(new Set());
  };

  const handleBronzeSchemaChange = (value: string) => {
    setBronzeSchema(value);
    setSelectedTables(new Set());
  };

  const prevSchemasKey = schemas.join(",");
  useEffect(() => {
    if (!catalog || schemas.length === 0) return;
    const vault =
      schemas.find((s) => VAULT_SCHEMA_HINTS.some((h) => s.toLowerCase().includes(h))) ?? "";
    const bronze = vault
      ? (schemas.find((s) => s !== vault) ?? schemas[0] ?? "")
      : (schemas[0] ?? "");
    setVaultSchema((prev) => (prev ? prev : vault));
    setBronzeSchema((prev) => (prev ? prev : bronze));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prevSchemasKey, catalog]);

  const toggleTable = useCallback((table: string) => {
    setSelectedTables((prev) => {
      const next = new Set(prev);
      if (next.has(table)) {
        next.delete(table);
      } else {
        next.add(table);
      }
      return next;
    });
  }, []);

  const handleSelectAll = () => {
    setSelectedTables(new Set(availableTables));
  };

  const handleDeselectAll = () => {
    setSelectedTables(new Set());
  };

  const buildPipelineRequest = () => {
    const systemId = env.defaults.systemId || catalog;
    return {
      catalog,
      bronze_schema: bronzeSchema,
      ...(vaultSchema ? { vault_schema: vaultSchema } : {}),
      tables: selectedTables.size > 0 ? Array.from(selectedTables) : [],
      system_id: systemId,
      system_name: env.defaults.systemName || catalog,
      source_type: systemId,
      record_source: env.defaults.recordSource || systemId,
    };
  };

  const handleSnapshot = () => {
    if (!catalog || !bronzeSchema) return;
    snapshot.mutate({
      catalog,
      bronze_schema: bronzeSchema,
      ...(vaultSchema ? { vault_schema: vaultSchema } : {}),
      tables: selectedTables.size > 0 ? Array.from(selectedTables) : [],
      ...(env.defaults.systemId ? { system_id: env.defaults.systemId } : {}),
      ...(env.defaults.systemName ? { system_name: env.defaults.systemName } : {}),
      ...(env.defaults.recordSource ? { record_source: env.defaults.recordSource } : {}),
    });
  };

  const runPipeline = useRunPipeline({
    onSuccess: (run) => {
      const req = buildPipelineRequest();
      void navigate({
        to: ROUTES.pipelineRun,
        search: {
          runId: run.run_id,
          req: encodeURIComponent(JSON.stringify(req)),
        } as never,
      });
    },
    onError: (err) => toast.error("Pipeline run failed", String(err.message)),
  });

  const canSubmit = Boolean(
    catalog && bronzeSchema && !snapshot.isPending && !runPipeline.isPending,
  );

  const handleRunPipeline = () => {
    if (!canSubmit) return;
    runPipeline.mutate(buildPipelineRequest());
  };

  return (
    <PageShell
      title={DISCOVERY_LABELS.pageTitle}
      description={DISCOVERY_LABELS.pageDescription}
      actions={
        <Button onClick={handleRunPipeline} disabled={!canSubmit}>
          {runPipeline.isPending ? <Spinner className="h-4 w-4" /> : null}
          {PIPELINE_LABELS.runButton}
        </Button>
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>{DISCOVERY_LABELS.cardTitle}</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              handleRunPipeline();
            }}
          >
            <FieldRow label={DISCOVERY_LABELS.catalog} htmlFor="catalog">
              <select
                id="catalog"
                value={catalog}
                onChange={(e) => handleCatalogChange(e.target.value)}
                className="mt-1 block w-full rounded border border-input bg-background px-2 py-1"
                disabled={catalogsLoading}
              >
                <option value="">{DISCOVERY_LABELS.selectCatalog}</option>
                {catalogs.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              {catalogsLoading && (
                <p className="mt-1 text-xs text-muted-foreground">{DISCOVERY_LABELS.loadingCatalogs}</p>
              )}
              {catalogsError && (
                <p className="mt-1 text-xs text-destructive">{String(catalogsError)}</p>
              )}
            </FieldRow>

            <FieldRow label={DISCOVERY_LABELS.bronzeSchema} htmlFor="bronzeSchema">
              <select
                id="bronzeSchema"
                value={bronzeSchema}
                onChange={(e) => handleBronzeSchemaChange(e.target.value)}
                className="mt-1 block w-full rounded border border-input bg-background px-2 py-1"
                disabled={!catalog || schemasLoading}
              >
                <option value="">
                  {catalog ? DISCOVERY_LABELS.selectBronzeSchema : DISCOVERY_LABELS.selectCatalogFirst}
                </option>
                {schemas.map((sch) => (
                  <option key={sch} value={sch}>
                    {sch}
                  </option>
                ))}
              </select>
            </FieldRow>

            <FieldRow label={DISCOVERY_LABELS.vaultSchema} htmlFor="vaultSchema">
              <select
                id="vaultSchema"
                value={vaultSchema}
                onChange={(e) => setVaultSchema(e.target.value)}
                className="mt-1 block w-full rounded border border-input bg-background px-2 py-1"
                disabled={!catalog || schemasLoading}
              >
                <option value="">
                  {catalog ? DISCOVERY_LABELS.selectVaultSchema : DISCOVERY_LABELS.selectCatalogFirst}
                </option>
                {schemas.map((sch) => (
                  <option key={sch} value={sch}>
                    {sch}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-muted-foreground">
                {DISCOVERY_LABELS.vaultSchemaHint}
              </p>
              {schemasLoading && (
                <p className="mt-1 text-xs text-muted-foreground">{DISCOVERY_LABELS.loadingSchemas}</p>
              )}
              {schemasError && (
                <p className="mt-1 text-xs text-destructive">{String(schemasError)}</p>
              )}
            </FieldRow>

            {bronzeSchema && (
              <FieldRow label={DISCOVERY_LABELS.tables} htmlFor="tables">
                <p className="mt-1 mb-2 text-xs text-muted-foreground">
                  {DISCOVERY_LABELS.tablesHint}
                </p>

                {tablesLoading ? (
                  <p className="text-xs text-muted-foreground">{DISCOVERY_LABELS.loadingTables}</p>
                ) : availableTables.length === 0 ? (
                  <p className="text-xs text-muted-foreground">{DISCOVERY_LABELS.selectSchemasFirst}</p>
                ) : (
                  <div className="rounded border border-input bg-background">
                    <div className="flex gap-3 border-b border-input px-3 py-2">
                      <button
                        type="button"
                        className="text-xs font-medium text-primary hover:underline disabled:opacity-40"
                        onClick={handleSelectAll}
                        disabled={allSelected}
                      >
                        {DISCOVERY_LABELS.selectAll}
                      </button>
                      <button
                        type="button"
                        className="text-xs font-medium text-muted-foreground hover:underline disabled:opacity-40"
                        onClick={handleDeselectAll}
                        disabled={selectedTables.size === 0}
                      >
                        {DISCOVERY_LABELS.deselectAll}
                      </button>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {selectedTables.size === 0
                          ? `All ${availableTables.length} tables`
                          : `${selectedTables.size} / ${availableTables.length} selected`}
                      </span>
                    </div>

                    <ul
                      id="tables"
                      className="max-h-56 overflow-y-auto divide-y divide-input"
                      role="listbox"
                      aria-multiselectable="true"
                      aria-label={DISCOVERY_LABELS.tables}
                    >
                      {availableTables.map((table) => {
                        const checked = selectedTables.has(table);
                        return (
                          <li key={table}>
                            <label className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-muted/50">
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => toggleTable(table)}
                                className="h-4 w-4 rounded border-input accent-primary"
                              />
                              <span className="font-mono text-sm">{table}</span>
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </FieldRow>
            )}

            <details className="rounded-md border border-dashed border-border bg-muted/30 px-4 py-3">
              <summary className="cursor-pointer text-sm font-medium text-foreground">
                {DISCOVERY_LABELS.advancedTitle}
              </summary>
              <div className="mt-3 space-y-3 text-sm text-muted-foreground">
                <p>{WORKFLOW_LABELS.discoveryAdvancedSummary}</p>
                <p className="font-mono text-xs">{WORKFLOW_LABELS.discoveryAdvancedSteps}</p>
                <Button
                  type="button"
                  intent="outline"
                  size="sm"
                  onClick={handleSnapshot}
                  disabled={!catalog || !bronzeSchema || snapshot.isPending}
                >
                  {snapshot.isPending ? <Spinner className="h-4 w-4" /> : null}
                  {DISCOVERY_LABELS.snapshot}
                </Button>
                {snapshot.error && (
                  <p className="text-destructive">
                    {DISCOVERY_LABELS.snapshotError} {String(snapshot.error)}
                  </p>
                )}
              </div>
            </details>
          </form>
        </CardContent>
      </Card>

      <p className="mt-4 text-center text-xs text-muted-foreground">
        <Link to={ROUTES.diff} className="text-primary hover:underline">
          Open advanced workflow
        </Link>
        {" · "}
        {WORKFLOW_LABELS.discoveryAdvancedSteps}
      </p>
    </PageShell>
  );
}
