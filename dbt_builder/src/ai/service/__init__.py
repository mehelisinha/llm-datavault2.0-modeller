"""Service facade: the *only* surface the API and UI may import.

Why a facade
------------
The architecture test (``tests/ai/test_architecture.py``) is being extended
to forbid the API / UI layers from reaching directly into ``ai.agents``,
``ai.pipeline``, ``ai.discovery``, ``ai.rendering`` or ``ai.embeddings``.
Routing every call through this facade means:

* every UI path is testable without spinning up FastAPI;
* refactors inside ``ai/*`` cannot accidentally break the UI;
* guardrails (validation, approval gate) can never be bypassed by a
  caller that imports an internal helper directly.

This module is intentionally thin: it composes the deterministic Steps 1-3,
the Validator (Step 6), and the approval store. LLM agents (Steps 4, 4b, 5)
are wired in during Phase B; the facade exposes stable method signatures
now so the API can be built against them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dbt_builder.src.ai.contracts.approval import ApprovalRecord, ApprovalStatus
from dbt_builder.src.ai.contracts.catalog import (
    BronzeSnapshot,
    CatalogSnapshot,
    ChangeSet,
)
from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.contracts.validation import ValidationReport
from dbt_builder.src.ai.pipeline import bronze_reader, catalog_inspector, diff_analyzer
from dbt_builder.src.ai.store import (
    ApprovalStore,
    SqliteApprovalStore,
    make_record,
)
from dbt_builder.src.ai.validation import validate as run_validation


class ApprovalGateError(RuntimeError):
    """Raised when a caller tries to approve a plan that has ERROR-severity issues."""


class DwaService:
    """High-level orchestration entry point used by the API."""

    def __init__(self, *, approval_store: ApprovalStore | None = None) -> None:
        self._store: ApprovalStore = approval_store or SqliteApprovalStore(
            Path(".cache") / "approvals.sqlite"
        )

    # ── Step 1 ──────────────────────────────────────────────────────────────
    def inspect_catalog(
        self,
        *,
        catalog: str,
        schema_name: str,
        list_entities: catalog_inspector.ListEntities,
        describe_table: catalog_inspector.DescribeTable,
        metadata_yaml_path: str | Path | None = None,
    ) -> CatalogSnapshot:
        return catalog_inspector.inspect_catalog(
            catalog=catalog,
            schema_name=schema_name,
            list_entities=list_entities,
            describe_table=describe_table,
            metadata_yaml_path=metadata_yaml_path,
        )

    # ── Step 2 ──────────────────────────────────────────────────────────────
    def read_bronze(
        self,
        *,
        catalog: str,
        schema_name: str,
        list_tables: bronze_reader.ListTables,
        describe_table: bronze_reader.DescribeTable,
        include_patterns: tuple[str, ...] = (),
        exclude_patterns: tuple[str, ...] = (),
    ) -> BronzeSnapshot:
        return bronze_reader.read_bronze(
            catalog=catalog,
            schema_name=schema_name,
            list_tables=list_tables,
            describe_table=describe_table,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )

    # ── Step 3 ──────────────────────────────────────────────────────────────
    def diff(self, catalog: CatalogSnapshot, bronze: BronzeSnapshot) -> ChangeSet:
        return diff_analyzer.diff(catalog, bronze)

    # ── Step 6 ──────────────────────────────────────────────────────────────
    def validate(
        self,
        *,
        plan: ModelingPlan | None = None,
        rendered_yaml: str | None = None,
        dbt_project_path: str | None = None,
    ) -> ValidationReport:
        return run_validation(
            plan=plan,
            rendered_yaml=rendered_yaml,
            dbt_project_path=dbt_project_path,
        )

    # ── Approval gate ───────────────────────────────────────────────────────
    def submit_for_review(
        self,
        *,
        plan: ModelingPlan,
        rendered_yaml: str,
        validation: ValidationReport,
        actor: str,
    ) -> ApprovalRecord:
        """Persist a DRAFT row. Always allowed."""
        record = make_record(
            plan_id=validation.plan_id,
            status=ApprovalStatus.DRAFT,
            actor=actor,
            plan_json=plan.model_dump_json(),
            validation_json=validation.model_dump_json(),
            previous_version=self._latest_version(validation.plan_id),
        )
        self._store.append(record)
        return record

    def approve(
        self,
        *,
        plan_id: str,
        actor: str,
        comment: str | None = None,
    ) -> ApprovalRecord:
        """Transition the latest DRAFT to APPROVED. Blocks on ERROR issues."""
        latest = self._store.latest(plan_id)
        if latest is None:
            raise ApprovalGateError(f"No plan found for plan_id={plan_id}")
        if latest.validation_json:
            report = ValidationReport.model_validate_json(latest.validation_json)
            if not report.passed:
                raise ApprovalGateError(
                    f"Cannot approve plan_id={plan_id}: "
                    f"{report.summary.errors} ERROR-severity issues outstanding."
                )
        record = make_record(
            plan_id=plan_id,
            status=ApprovalStatus.APPROVED,
            actor=actor,
            plan_json=latest.plan_json,
            validation_json=latest.validation_json,
            comment=comment,
            previous_version=latest.version,
        )
        self._store.append(record)
        return record

    def reject(
        self,
        *,
        plan_id: str,
        actor: str,
        comment: str,
    ) -> ApprovalRecord:
        latest = self._store.latest(plan_id)
        if latest is None:
            raise ApprovalGateError(f"No plan found for plan_id={plan_id}")
        record = make_record(
            plan_id=plan_id,
            status=ApprovalStatus.REJECTED,
            actor=actor,
            plan_json=latest.plan_json,
            validation_json=latest.validation_json,
            comment=comment,
            previous_version=latest.version,
        )
        self._store.append(record)
        return record

    def request_changes(
        self,
        *,
        plan_id: str,
        actor: str,
        comment: str,
    ) -> ApprovalRecord:
        latest = self._store.latest(plan_id)
        if latest is None:
            raise ApprovalGateError(f"No plan found for plan_id={plan_id}")
        record = make_record(
            plan_id=plan_id,
            status=ApprovalStatus.CHANGES_REQUESTED,
            actor=actor,
            plan_json=latest.plan_json,
            validation_json=latest.validation_json,
            comment=comment,
            previous_version=latest.version,
        )
        self._store.append(record)
        return record

    def history(self, plan_id: str) -> tuple[ApprovalRecord, ...]:
        return self._store.history(plan_id)

    def list_recent(self, *, limit: int = 50) -> tuple[ApprovalRecord, ...]:
        return self._store.list_recent(limit=limit)

    # ── helpers ─────────────────────────────────────────────────────────────
    def _latest_version(self, plan_id: str) -> int | None:
        latest = self._store.latest(plan_id)
        return latest.version if latest else None

    @staticmethod
    def _now() -> datetime:
        # Centralised so tests can monkeypatch it.
        return datetime.now(timezone.utc)


# Convenience singleton for the API (override in tests via dependency_overrides).
_default_service: DwaService | None = None


def get_service() -> DwaService:
    global _default_service
    if _default_service is None:
        _default_service = DwaService()
    return _default_service


def set_service(service: DwaService | None) -> None:
    """Replace the singleton (used by tests)."""
    global _default_service
    _default_service = service


def _appease_unused_import(_: Any) -> None:  # pragma: no cover
    """Keep ``Any`` import — used by future typed kwargs."""
    return None
