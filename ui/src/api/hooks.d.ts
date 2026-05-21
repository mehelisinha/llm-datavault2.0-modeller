import type { UseMutationOptions, UseQueryOptions } from "@tanstack/react-query";
import type { operations } from "./schema";
import type { CatalogListResponse, SchemaListResponse, SnapshotResponse } from "./types";
type AnalyzeBody = operations["analyze_api_plans_analyze_post"]["requestBody"]["content"]["application/json"];
type ValidateBody = operations["validate_api_plans_validate_post"]["requestBody"]["content"]["application/json"];
type GenerateBody = operations["generate_api_plans_generate_post"]["requestBody"]["content"]["application/json"];
type ArchitectBody = operations["architect_bv_api_plans_architect_bv_post"]["requestBody"]["content"]["application/json"];
type SnapshotBody = operations["snapshot_api_discovery_snapshot_post"]["requestBody"]["content"]["application/json"];
type SubmitBody = operations["submit_for_review_api_plans__plan_id__submit_for_review_post"]["requestBody"]["content"]["application/json"];
type ValidationReport = operations["validate_api_plans_validate_post"]["responses"]["200"]["content"]["application/json"];
type ModelingPlan = operations["analyze_api_plans_analyze_post"]["responses"]["200"]["content"]["application/json"];
export declare function useCatalogs(options?: UseQueryOptions<CatalogListResponse, Error>): import("@tanstack/react-query").UseQueryResult<{
    catalogs: string[];
}, Error>;
export declare function useSchemas(catalog: string | null, options?: UseQueryOptions<SchemaListResponse, Error>): import("@tanstack/react-query").UseQueryResult<{
    catalog: string;
    schemas: string[];
}, Error>;
export declare function useDiscoverySnapshot(options?: UseMutationOptions<SnapshotResponse, Error, SnapshotBody>): import("@tanstack/react-query").UseMutationResult<{
    system: import("./schema").components["schemas"]["SourceSystem"];
    catalog_snapshot: import("./schema").components["schemas"]["CatalogSnapshot"];
    bronze_snapshot: import("./schema").components["schemas"]["BronzeSnapshot"];
    change_set: import("./schema").components["schemas"]["ChangeSet"];
}, Error, {
    catalog: string;
    bronze_schema: string;
    vault_schema: string;
    system_id?: string | null;
    system_name?: string | null;
    record_source?: string | null;
    metadata_yaml_path?: string | null;
    include_patterns?: string[];
    exclude_patterns?: string[];
}, unknown>;
export declare function useValidatePlan(options?: UseMutationOptions<ValidationReport, Error, ValidateBody>): import("@tanstack/react-query").UseMutationResult<{
    plan_id: string;
    computed_at: string;
    issues: import("./schema").components["schemas"]["ValidationIssue"][];
    summary: import("./schema").components["schemas"]["CheckSummary"];
    checks_run: string[];
}, Error, {
    plan?: import("./schema").components["schemas"]["ModelingPlan-Input"] | null;
    rendered_yaml?: string | null;
    dbt_project_path?: string | null;
}, unknown>;
export declare function useAnalyzePlan(options?: UseMutationOptions<ModelingPlan, Error, AnalyzeBody>): import("@tanstack/react-query").UseMutationResult<{
    system_id: string;
    hubs: import("./schema").components["schemas"]["HubDecision"][];
    links: import("./schema").components["schemas"]["LinkDecision"][];
    satellites: import("./schema").components["schemas"]["SatelliteDecision"][];
}, Error, {
    system: import("./schema").components["schemas"]["SourceSystem"];
    bronze: import("./schema").components["schemas"]["BronzeSnapshot"];
    change_set: import("./schema").components["schemas"]["ChangeSet"];
}, unknown>;
export declare function useArchitectBv(options?: UseMutationOptions<operations["architect_bv_api_plans_architect_bv_post"]["responses"]["200"]["content"]["application/json"], Error, ArchitectBody>): import("@tanstack/react-query").UseMutationResult<{
    system_id: string;
    pit_tables: import("./schema").components["schemas"]["PitTable"][];
    bridge_tables: import("./schema").components["schemas"]["BridgeTable"][];
    bv_satellites: import("./schema").components["schemas"]["BvSatellite"][];
}, Error, {
    system_id: string;
    hubs: import("./schema").components["schemas"]["HubDecision"][];
    links: import("./schema").components["schemas"]["LinkDecision"][];
    satellites: import("./schema").components["schemas"]["SatelliteDecision"][];
}, unknown>;
export declare function useGenerateYaml(options?: UseMutationOptions<operations["generate_api_plans_generate_post"]["responses"]["200"]["content"]["application/json"], Error, GenerateBody>): import("@tanstack/react-query").UseMutationResult<{
    files: import("./schema").components["schemas"]["GeneratedYamlFile"][];
}, Error, {
    plan: import("./schema").components["schemas"]["ModelingPlan-Input"];
    bv?: import("./schema").components["schemas"]["BvProposal"] | null;
}, unknown>;
export declare function useSubmitForReview(planId: string, options?: UseMutationOptions<unknown, Error, SubmitBody>): import("@tanstack/react-query").UseMutationResult<unknown, Error, {
    plan: import("./schema").components["schemas"]["ModelingPlan"];
    rendered_yaml: string;
    validation: import("./schema").components["schemas"]["ValidationReport"];
}, unknown>;
export declare function useApprovePlan(planId: string, options?: UseMutationOptions<unknown, Error, operations["approve_api_plans__plan_id__approve_post"]["requestBody"]["content"]["application/json"]>): import("@tanstack/react-query").UseMutationResult<unknown, Error, {
    comment?: string | null;
}, unknown>;
export declare function useRejectPlan(planId: string, options?: UseMutationOptions<unknown, Error, operations["reject_api_plans__plan_id__reject_post"]["requestBody"]["content"]["application/json"]>): import("@tanstack/react-query").UseMutationResult<unknown, Error, {
    comment: string;
}, unknown>;
export declare function useRequestChanges(planId: string, options?: UseMutationOptions<unknown, Error, operations["request_changes_api_plans__plan_id__request_changes_post"]["requestBody"]["content"]["application/json"]>): import("@tanstack/react-query").UseMutationResult<unknown, Error, {
    comment: string;
}, unknown>;
export declare function useHistory(options?: UseQueryOptions<operations["list_recent_api_history_get"]["responses"]["200"]["content"]["application/json"], Error>): import("@tanstack/react-query").UseQueryResult<{
    plan_id: string;
    version: number;
    status: import("./schema").components["schemas"]["ApprovalStatus"];
    actor: string;
    timestamp: string;
    comment?: string | null;
    plan_json: string;
    validation_json?: string | null;
    parent_plan_id?: string | null;
}[], Error>;
export declare function useHistoryFor(planId: string, options?: UseQueryOptions<unknown, Error>): import("@tanstack/react-query").UseQueryResult<unknown, Error>;
export declare function useHealth(options?: UseQueryOptions<{
    status: string;
}, Error>): import("@tanstack/react-query").UseQueryResult<{
    status: string;
}, Error>;
export {};
