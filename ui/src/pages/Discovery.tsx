import { useCallback, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { useCatalogs, useDiscoverySnapshot, useSchemas, useSchemaTables } from "@/api/hooks";
import { PageShell } from "@/components/PageShell";
import { Button, Card, CardContent, CardHeader, CardTitle, Spinner } from "@/components/ui";
import { DISCOVERY_LABELS } from "@/constants/discovery";
import { ROUTES } from "@/constants/routes";
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

  const [catalog, setCatalog] = useState<string>("");
  const [bronzeSchema, setBronzeSchema] = useState<string>("");
  const [vaultSchema, setVaultSchema] = useState<string>("");
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

  // Auto-select defaults once schemas arrive for the chosen catalog.
  const prevSchemasKey = schemas.join(",");
  useMemo(() => {
    if (!catalog || schemas.length === 0) return;
    const vault =
      schemas.find((s) => VAULT_SCHEMA_HINTS.some((h) => s.toLowerCase().includes(h))) ?? "";
    const bronze = schemas.find((s) => s !== vault) ?? schemas[0] ?? "";
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

  const handleSnapshot = () => {
    if (!catalog || !bronzeSchema || !vaultSchema) return;
    snapshot.mutate({
      catalog,
      bronze_schema: bronzeSchema,
      vault_schema: vaultSchema,
      // Pass selected tables; empty means "all" (backend default).
      tables: selectedTables.size > 0 ? Array.from(selectedTables) : [],
      ...(env.defaults.systemId ? { system_id: env.defaults.systemId } : {}),
      ...(env.defaults.systemName ? { system_name: env.defaults.systemName } : {}),
      ...(env.defaults.recordSource ? { record_source: env.defaults.recordSource } : {}),
    });
  };

  const canSnapshot = Boolean(catalog && bronzeSchema && vaultSchema && !snapshot.isPending);

  return (
    <PageShell
      title={DISCOVERY_LABELS.pageTitle}
      description={DISCOVERY_LABELS.pageDescription}
      actions={
        <Button onClick={handleSnapshot} disabled={!canSnapshot}>
          {snapshot.isPending ? <Spinner className="h-4 w-4" /> : null}
          {DISCOVERY_LABELS.snapshot}
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
              handleSnapshot();
            }}
          >
            {/* ── Catalog ────────────────────────────────────────────── */}
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

            {/* ── Bronze schema ───────────────────────────────────────── */}
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

            {/* ── Vault schema ────────────────────────────────────────── */}
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
              {schemasLoading && (
                <p className="mt-1 text-xs text-muted-foreground">{DISCOVERY_LABELS.loadingSchemas}</p>
              )}
              {schemasError && (
                <p className="mt-1 text-xs text-destructive">{String(schemasError)}</p>
              )}
            </FieldRow>

            {/* ── Table multi-select ──────────────────────────────────── */}
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
                    {/* Select all / deselect all toolbar */}
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

                    {/* Scrollable checkbox list */}
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

            {snapshot.error && (
              <p className="text-sm text-destructive">
                {DISCOVERY_LABELS.snapshotError} {String(snapshot.error)}
              </p>
            )}
          </form>
        </CardContent>
      </Card>
    </PageShell>
  );
}
