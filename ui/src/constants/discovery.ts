/**
 * Discovery domain constants.
 */

export const DISCOVERY_LABELS = Object.freeze({
  catalog: "Catalog",
  bronzeSchema: "Bronze schema",
  vaultSchema: "Vault schema",
  selectCatalog: "Select a catalog",
  selectBronzeSchema: "Select a bronze schema",
  selectVaultSchema: "Select a vault schema",
  selectCatalogFirst: "Select a catalog first",
  pageTitle: "Discovery",
  pageDescription: "Pick catalog and schemas, then snapshot bronze and build a change set.",
  cardTitle: "Catalog inspection",
  snapshot: "Run snapshot",
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
