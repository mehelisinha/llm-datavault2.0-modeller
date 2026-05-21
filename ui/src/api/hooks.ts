import { useMutation, useQuery } from "@tanstack/react-query";
import type { UseMutationOptions, UseQueryOptions } from "@tanstack/react-query";

import { unwrapApiResult } from "@/lib/apiResult";

import { api } from "./client";
import type { operations } from "./schema";
import type {
  CatalogListResponse,
  GenerateResponse,
  SchemaListResponse,
  SnapshotResponse,
  TableListResponse,
} from "./types";

type AnalyzeBody =
  operations["analyze_api_plans_analyze_post"]["requestBody"]["content"]["application/json"];
type ValidateBody =
  operations["validate_api_plans_validate_post"]["requestBody"]["content"]["application/json"];
type ArchitectBody =
  operations["architect_bv_api_plans_architect_bv_post"]["requestBody"]["content"]["application/json"];
// Extend the generated SnapshotBody with the new optional `tables` field
// (added to the backend but not yet in the generated schema.d.ts).
type SnapshotBody =
  operations["snapshot_api_discovery_snapshot_post"]["requestBody"]["content"]["application/json"] & {
    tables?: string[];
  };

// GenerateBody extends the schema with fields added to the backend but not yet
// reflected in the generated schema.d.ts (format + system).
type _GenerateBodyBase =
  operations["generate_api_plans_generate_post"]["requestBody"]["content"]["application/json"];
type GenerateBody = Omit<_GenerateBodyBase, "format"> & {
  system?: import("./types").SourceSystem | null;
  format?: "metadata_v3" | "dbt_per_file";
};
type SubmitBody =
  operations["submit_for_review_api_plans__plan_id__submit_for_review_post"]["requestBody"]["content"]["application/json"];
type ValidationReport =
  operations["validate_api_plans_validate_post"]["responses"]["200"]["content"]["application/json"];
type ModelingPlan =
  operations["analyze_api_plans_analyze_post"]["responses"]["200"]["content"]["application/json"];

export function useCatalogs(options?: UseQueryOptions<CatalogListResponse, Error>) {
  return useQuery({
    queryKey: ["discovery", "catalogs"],
    queryFn: async () => {
      const res = await api.GET("/api/discovery/catalogs");
      return unwrapApiResult(res) as CatalogListResponse;
    },
    ...options,
  });
}

export function useSchemas(
  catalog: string | null,
  options?: UseQueryOptions<SchemaListResponse, Error>,
) {
  return useQuery({
    queryKey: ["discovery", "schemas", catalog],
    enabled: Boolean(catalog),
    queryFn: async () => {
      const res = await api.GET("/api/discovery/catalogs/{catalog}/schemas", {
        params: { path: { catalog: catalog! } },
      });
      return unwrapApiResult(res) as SchemaListResponse;
    },
    ...options,
  });
}

export function useDiscoverySnapshot(
  options?: UseMutationOptions<SnapshotResponse, Error, SnapshotBody>,
) {
  return useMutation({
    mutationFn: async (body) => {
      const res = await api.POST("/api/discovery/snapshot", { body });
      return unwrapApiResult(res) as SnapshotResponse;
    },
    ...options,
  });
}

export function useSchemaTables(
  catalog: string | null,
  schema: string | null,
  options?: UseQueryOptions<TableListResponse, Error>,
) {
  return useQuery({
    queryKey: ["discovery", "tables", catalog, schema],
    enabled: Boolean(catalog) && Boolean(schema),
    queryFn: async () => {
      const res = await api.GET(
        "/api/discovery/catalogs/{catalog}/schemas/{schema}/tables" as any,
        { params: { path: { catalog: catalog!, schema: schema! } } },
      );
      return unwrapApiResult(res) as TableListResponse;
    },
    ...options,
  });
}

export function useValidatePlan(
  options?: UseMutationOptions<ValidationReport, Error, ValidateBody>,
) {
  return useMutation({
    mutationFn: async (body) => {
      const res = await api.POST("/api/plans/validate", { body });
      return unwrapApiResult(res);
    },
    ...options,
  });
}

export function useAnalyzePlan(
  options?: UseMutationOptions<ModelingPlan, Error, AnalyzeBody>,
) {
  return useMutation({
    mutationFn: async (body) => {
      const res = await api.POST("/api/plans/analyze", { body });
      return unwrapApiResult(res);
    },
    ...options,
  });
}

export function useArchitectBv(
  options?: UseMutationOptions<
    operations["architect_bv_api_plans_architect_bv_post"]["responses"]["200"]["content"]["application/json"],
    Error,
    ArchitectBody
  >,
) {
  return useMutation({
    mutationFn: async (body) => {
      const res = await api.POST("/api/plans/architect-bv", { body });
      return unwrapApiResult(res);
    },
    ...options,
  });
}

export function useGenerateYaml(
  options?: UseMutationOptions<GenerateResponse, Error, GenerateBody>,
) {
  return useMutation({
    mutationFn: async (body) => {
      const res = await api.POST("/api/plans/generate", { body: body as any });
      return unwrapApiResult(res) as GenerateResponse;
    },
    ...options,
  });
}

export function useSubmitForReview(
  planId: string,
  options?: UseMutationOptions<unknown, Error, SubmitBody>,
) {
  return useMutation({
    mutationFn: async (body) => {
      const res = await api.POST("/api/plans/{plan_id}/submit-for-review", {
        params: { path: { plan_id: planId } },
        body,
      });
      return unwrapApiResult(res);
    },
    ...options,
  });
}

export function useApprovePlan(
  planId: string,
  options?: UseMutationOptions<
    unknown,
    Error,
    operations["approve_api_plans__plan_id__approve_post"]["requestBody"]["content"]["application/json"]
  >,
) {
  return useMutation({
    mutationFn: async (body) => {
      const res = await api.POST("/api/plans/{plan_id}/approve", {
        params: { path: { plan_id: planId } },
        body,
      });
      return unwrapApiResult(res);
    },
    ...options,
  });
}

export function useRejectPlan(
  planId: string,
  options?: UseMutationOptions<
    unknown,
    Error,
    operations["reject_api_plans__plan_id__reject_post"]["requestBody"]["content"]["application/json"]
  >,
) {
  return useMutation({
    mutationFn: async (body) => {
      const res = await api.POST("/api/plans/{plan_id}/reject", {
        params: { path: { plan_id: planId } },
        body,
      });
      return unwrapApiResult(res);
    },
    ...options,
  });
}

export function useRequestChanges(
  planId: string,
  options?: UseMutationOptions<
    unknown,
    Error,
    operations["request_changes_api_plans__plan_id__request_changes_post"]["requestBody"]["content"]["application/json"]
  >,
) {
  return useMutation({
    mutationFn: async (body) => {
      const res = await api.POST("/api/plans/{plan_id}/request-changes", {
        params: { path: { plan_id: planId } },
        body,
      });
      return unwrapApiResult(res);
    },
    ...options,
  });
}

export function useHistory(
  options?: UseQueryOptions<
    operations["list_recent_api_history_get"]["responses"]["200"]["content"]["application/json"],
    Error
  >,
) {
  return useQuery({
    queryKey: ["history"],
    queryFn: async () => {
      const res = await api.GET("/api/history", {});
      return unwrapApiResult(res);
    },
    ...options,
  });
}

export function useHistoryFor(planId: string, options?: UseQueryOptions<unknown, Error>) {
  return useQuery({
    queryKey: ["history", planId],
    queryFn: async () => {
      const res = await api.GET("/api/history/{plan_id}", {
        params: { path: { plan_id: planId } },
      });
      return unwrapApiResult(res);
    },
    ...options,
  });
}

export function useHealth(options?: UseQueryOptions<{ status: string }, Error>) {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const res = await api.GET("/health");
      return unwrapApiResult(res) as { status: string };
    },
    ...options,
  });
}
