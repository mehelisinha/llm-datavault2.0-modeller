# Storage Layer & GitLab MR Publisher Implementation Details

This document details the code changes, new components, and architectural reasoning applied during the implementation of the post-approval storage layer and GitLab MR publisher for the DWA AI metadata pipeline.

## 1. Overview
The goal of this implementation is to persist the AI-generated and user-approved YAML metadata into targeted storage backends and securely publish them to GitLab via Merge Requests. 

The implementation carefully augments the **existing** approval state machine (`DRAFT` → `APPROVED` / `REJECTED` / `CHANGES_REQUESTED`) inside `DwaService.approve`, avoiding parallel or duplicate state machines. It operates on a **fail-soft** model where external system failures (e.g., Databricks or GitLab downtime) do not interrupt the core application state or crash the application.

## 2. Components Introduced

### 2.1 Settings & Environment (`dwa/dbt_builder/src/ai/settings.py` & `.env`)
- **Added `DWA_AI_METADATA_STORE_BACKEND`:** Can be set to `auto`, `local`, `adls`, or `delta`.
- **Added Databricks Configs:** `DWA_AI_DATABRICKS_WORKSPACE_URL`, `HTTP_PATH`, `TOKEN` and Delta table mappings `DWA_AI_METADATA_DELTA_CATALOG`, `SCHEMA`, `YAML_TABLE`, `APPROVALS_TABLE`.
- **Added GitLab Configs:** `DWA_AI_GITLAB_BASE_URL`, `TOKEN`, `PROJECT_ID`, `DEFAULT_BRANCH`, `STORAGE_ROOT_BRANCH`, and path/title templates.
- **Reason:** Keeps the application completely environment-driven. Default configurations heavily favour safe development experiences.

### 2.2 Databricks SQL Executor (`dwa/dbt_builder/src/utils/databricks_sql.py`)
- Added a thin wrapper `DatabricksSqlExecutor` to handle low-level connections to Databricks SQL Warehouses securely using `databricks-sql-connector`. Uses thread locking.
- **Reason:** Provides a single, safe interface for the Delta stores to run SQL queries.

### 2.3 Delta Storage Backends (`dwa/dbt_builder/src/ai/store/__init__.py` & `dwa/dbt_builder/src/utils/yaml_store.py`)
- **`DeltaYamlStore`**: Implements the `YamlStore` protocol. Runs `CREATE TABLE IF NOT EXISTS` using Delta, partitioned by catalog. Stores `catalog, plan_id, version, yaml_text, yaml_sha256, created_at`.
- **`DeltaApprovalStore`**: Implements the `ApprovalStore` protocol for audit. Since Delta lacks PK constraints, it runs a pre-check `SELECT 1 ... LIMIT 1` to prevent duplicate `(plan_id, version)` entries.
- **Backend Dispatch:** Modded `make_yaml_store` and `make_approval_store` factories to dynamically load stores depending on the `metadata_store_backend` configuration (with safe fallbacks to `SqliteApprovalStore` and `LocalYamlStore`).

### 2.4 GitLab MR Publisher (`dwa/dbt_builder/src/utils/gitlab_mr.py` & `dwa/dbt_builder/src/ai/integrations/gitlab.py`)
- Developed `GitLabMrPublisher` integrating with GitLab API v4.
- **Workflow:** 
  1. Bootstraps the storage branch (`approved-yaml`) dynamically from the read-only root (`main`) on first use if it does not exist (cached for subsequent calls).
  2. Creates a dedicated feature branch from the storage branch. Handles idempotency (400 branch already exists) gracefully.
  3. Commits the YAML payload (updates if it exists, creates if it doesn't).
  4. Opens a Merge Request targeting the storage branch. Handles MR conflicts (409) gracefully by returning the existing MR URL.
- **Safety Guardrails:** Raises a `ValueError` during initialisation if it detects an attempt to target `main` or `master`. 
- **Reason:** Ensure `main` is completely protected. Fully automates pushing approved content to Git without overriding the human's right to execute the final merge.

## 3. Bug Fixes & Refinements

### 3.1 Catalog Identifier Fix (`dwa/dbt_builder/src/utils/yaml_store.py`)
- **Issue:** All approved YAMLs were being saved to `catalogs/unknown/...` because the pipeline's metadata emitter used `system.system_id` while the backend expected `system.catalog`.
- **Fix:** Upgraded `catalog_from_yaml` to check for `system.catalog` and gracefully fallback to `system.system_id`. 
- **Tests Added:** Covered via new tests in `dwa/tests/ai/test_catalog_from_yaml.py`.

### 3.2 Service Wiring (`dwa/dbt_builder/src/ai/service/__init__.py`)
- Rewired `DwaService.approve` to accommodate the YAML store mapping and GitLab MR publisher sequentially.
- **Fail-Soft Enforcement:** Both Delta save and GitLab publish are executed within generic `try/except` catch-alls. Failures are logged, but the Approval Record completes safely.

## 4. Test Coverage Added
- `test_delta_yaml_store.py` (6 tests for Delta query structures)
- `test_delta_approval_store.py` (7 tests, covering duplicates, limits, history)
- `test_gitlab_mr_publisher.py` (10 tests, evaluating idempotency, conflict, path encoding, branch guards)
- `test_service_gitlab_wiring.py` (3 tests asserting DwaService behaviour and error absorption)
- `test_store_factories.py` (7 tests to check dispatch logic given variable mock environments)
- `test_catalog_from_yaml.py` (5 tests locking down fallback and string match behaviour)
- Architecture test updated to properly whitelist the new `utils/gitlab_mr.py` and `utils/databricks_sql.py` namespaces.

## 5. Architectural Conclusions
The system treats the target storage and publishing steps purely as downstream side-effects of an approval. While Databricks Delta serves excellently for analytics, storing OLTP state (approvals audit) within Delta carries latency and cost overheads for serverless. Moving forward, GitLab maintains the source-of-truth configuration, and `SqliteApprovalStore` (with future migrations to Postgres) ensures safe transactionality for the State Machine operations, abstracting dependencies on external big-data tools.