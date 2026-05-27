/**
 * Discovery domain constants.
 */

export const DISCOVERY_LABELS = Object.freeze({
  catalog: "Catalog",
  bronzeSchema: "Bronze schema",
  vaultSchema: "Vault schema (optional)",
  selectCatalog: "Select a catalog",
  selectBronzeSchema: "Select a bronze schema",
  selectVaultSchema: "(leave empty for greenfield)",
  selectCatalogFirst: "Select a catalog first",
  vaultSchemaHint:
    "Where existing hub_/lnk_/sat_ tables live. Leave empty for a first-time build — every bronze table will be classified as NEW.",
  pageTitle: "Generate Vault",
  pageDescription:
    "Pick catalog and bronze schema, then run the full pipeline to produce metadata YAML.",
  cardTitle: "Source selection",
  advancedTitle: "Advanced workflow",
  advancedOpen: "Show step-by-step workflow",
  advancedClose: "Hide step-by-step workflow",
  snapshot: "Run snapshot only",
  snapshotSuccess: "Snapshot complete — continue to Diff.",
  snapshotError: "Snapshot failed.",
  loadingCatalogs: "Loading catalogs…",
  loadingSchemas: "Loading schemas…",
  // Table multi-select
  tables: "Source tables",
  selectSchemasFirst: "Select schemas first",
  loadingTables: "Loading tables…",
  tablesHint: "Select the tables to include. Leave empty to include all tables in the schema.",
  selectAll: "Select all",
  deselectAll: "Deselect all",
});
