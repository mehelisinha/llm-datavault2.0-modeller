/**
 * Pipeline-run types & labels.
 *
 * The backend wire format mirrors :class:`PipelineRun` in
 * ``dbt_builder/src/ai/contracts/pipeline_run.py``. Keep these in sync
 * (or generate them from the OpenAPI schema once the route stabilises).
 */
import type {
  BvProposal,
  CatalogSnapshot,
  BronzeSnapshot,
  ChangeSet,
  ModelingPlan,
  SourceSystem,
  ValidationReport,
} from "@/api/types";

export type PipelineRunStatus = "running" | "paused" | "done" | "failed";

export type PipelineStepName =
  | "snapshot"
  | "analyze"
  | "architect_bv"
  | "generate"
  | "validate";

export type PipelineStepStatus = "ok" | "failed" | "skipped";

export type PipelineStepResult = {
  step: PipelineStepName;
  status: PipelineStepStatus;
  duration_ms: number;
  error: string | null;
};

export type RiskSeverity = "low" | "medium" | "high";

export type RiskKind =
  | "high_new_table_volume"
  | "high_drift_fraction"
  | "orphaned_entities_present"
  | "low_confidence_decisions"
  | "empty_plan"
  | "validation_errors"
  | "validation_warnings";

export type SupervisionRecommendation = "pass" | "pause";

export type RiskSignal = {
  kind: RiskKind;
  severity: RiskSeverity;
  detail: string;
};

export type RiskAssessment = {
  assessed_after_step: string;
  signals: RiskSignal[];
  max_severity: RiskSeverity;
  recommendation: SupervisionRecommendation;
};

export type PipelineRun = {
  run_id: string;
  status: PipelineRunStatus;
  stop_after: string | null;
  created_at: string;
  updated_at: string;
  steps: PipelineStepResult[];
  system: SourceSystem | null;
  catalog_snapshot: CatalogSnapshot | null;
  bronze_snapshot: BronzeSnapshot | null;
  change_set: ChangeSet | null;
  plan: ModelingPlan | null;
  bv: BvProposal | null;
  validation: ValidationReport | null;
  rendered_yaml: string | null;
  error_detail: string | null;
  risk_assessment: RiskAssessment | null;
};

export type PipelineRunRequest = {
  catalog: string;
  bronze_schema: string;
  /** Omit for greenfield builds (diff classifies every bronze table as NEW). */
  vault_schema?: string;
  system_id: string;
  system_name: string;
  source_type: string;
  record_source?: string;
  /** Explicit table allowlist; empty means all tables in the bronze schema. */
  tables?: string[];
  include_patterns?: string[];
  exclude_patterns?: string[];
  acknowledge_risks?: boolean;
};

// ── Display labels ───────────────────────────────────────────────────────────

export const STEP_LABELS: Readonly<Record<PipelineStepName, string>> = Object.freeze({
  snapshot: "Discover bronze tables",
  analyze: "Build modelling plan",
  architect_bv: "Design business vault",
  generate: "Render YAML",
  validate: "Validate output",
});

export const STATUS_LABELS: Readonly<Record<PipelineRunStatus, string>> = Object.freeze({
  running: "Running",
  paused: "Paused for review",
  done: "Complete",
  failed: "Failed",
});

export const RISK_KIND_LABELS: Readonly<Record<RiskKind, string>> = Object.freeze({
  high_new_table_volume: "Many new tables",
  high_drift_fraction: "High schema drift",
  orphaned_entities_present: "Orphaned entities",
  low_confidence_decisions: "Low-confidence decisions",
  empty_plan: "Empty plan",
  validation_errors: "Validation errors",
  validation_warnings: "Validation warnings",
});

export const PIPELINE_LABELS = Object.freeze({
  pageTitle: "Pipeline run",
  pageDescription:
    "Watch the assistant build your YAML. Review any risks the supervisor surfaces, then approve.",
  runButton: "Generate Vault",
  ackButton: "Continue anyway",
  approveButton: "Approve",
  empty: "No pipeline run in progress.",
  noYaml: "YAML will appear here when the pipeline completes.",
  riskBanner: "The supervisor wants you to take a look before continuing.",
  sectionTimeline: "Progress",
  sectionDiff: "Bronze diff",
  sectionPlan: "Modelling plan",
  sectionBv: "Business vault proposal",
  sectionValidation: "Validation",
  sectionYaml: "Generated YAML",
  sectionGovernance: "Decision",
  downloadButton: "Download YAML",
  downloadFilename: (systemId: string) => `${systemId || "metadata"}.yaml`,
});
