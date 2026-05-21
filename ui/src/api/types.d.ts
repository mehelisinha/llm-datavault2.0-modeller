/**
 * API entity types inferred from the OpenAPI schema.
 */
import type { components } from "./schema";
export type SourceSystem = components["schemas"]["SourceSystem"];
export type BronzeSnapshot = components["schemas"]["BronzeSnapshot"];
export type ChangeSet = components["schemas"]["ChangeSet"];
export type TableChange = components["schemas"]["TableChange"];
export type ModelingPlan = components["schemas"]["ModelingPlan-Output"];
export type BvProposal = components["schemas"]["BvProposal"];
export type ValidationReport = components["schemas"]["ValidationReport"];
export type GeneratedYamlFile = components["schemas"]["GeneratedYamlFile"];
export type ApprovalRecord = components["schemas"]["ApprovalRecord"];
export type CatalogSnapshot = components["schemas"]["CatalogSnapshot"];
export type SnapshotResponse = components["schemas"]["SnapshotResponse"];
export type CatalogListResponse = components["schemas"]["CatalogListResponse"];
export type SchemaListResponse = components["schemas"]["SchemaListResponse"];
export declare function validationPassed(report: ValidationReport): boolean;
