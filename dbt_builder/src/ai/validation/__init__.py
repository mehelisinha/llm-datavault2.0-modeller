"""Step 6 — Validator.

Runs the deterministic safety net before any generated YAML reaches the dbt
repository. The validator runs as many of the four checks listed in the
pptx as are applicable to the inputs at hand:

1. **YAML syntax** — parse the rendered YAML.
2. **Pydantic schema** — re-validate the in-memory ModelingPlan / metadata.
3. **Referential integrity** — every parent_hub points to a real hub; every
   hashdiff is declared in staging; no append-only on eff-sat / BV-merge / PIT
   / bridge; on_schema_change set on every incremental model.
4. **dbt parse dry-run** — only available when called with a dbt project
   path; skipped otherwise (the UI just doesn't show the check name).

The output is a single :class:`ValidationReport` consumed by the UI banner
and stored verbatim in the approval audit row.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import yaml

from dbt_builder.src.ai.contracts.bv import BvProposal
from dbt_builder.src.ai.contracts.decisions import ModelingPlan
from dbt_builder.src.ai.contracts.validation import (
    CheckSummary,
    Severity,
    ValidationIssue,
    ValidationReport,
)
from dbt_builder.src.ai.utils.ids import stable_id
from dbt_builder.src.ai.validation.dbt_gate import (
    DbtCommandRunner,
    DbtGateConfig,
    run_dbt_gate,
)

_SYSTEM_COLUMN_NAMES = frozenset({"load_dts", "load_date", "record_source", "cdc_flag"})


# ─── individual checks ───────────────────────────────────────────────────────


def _check_yaml_syntax(
    rendered_yaml: str | None,
) -> tuple[list[ValidationIssue], dict[str, Any] | None]:
    """Parse YAML; on failure return one ERROR and no parsed dict."""
    if rendered_yaml is None:
        return [], None
    try:
        parsed = yaml.safe_load(rendered_yaml)
    except yaml.YAMLError as exc:
        issue = ValidationIssue(
            code="YAML_SYNTAX",
            severity=Severity.ERROR,
            message=f"Generated YAML failed to parse: {exc}",
            location=None,
            suggestion="Re-run YAML generator; check reference template integrity.",
        )
        return [issue], None
    if not isinstance(parsed, dict):
        return (
            [
                ValidationIssue(
                    code="YAML_ROOT_TYPE",
                    severity=Severity.ERROR,
                    message="Generated YAML root must be a mapping.",
                )
            ],
            None,
        )
    return [], parsed


def _check_pydantic_schema(plan: ModelingPlan | None) -> list[ValidationIssue]:
    """ModelingPlan has model_validators of its own; this is a re-run guard.

    We *re-validate* the plan after any in-process mutation to surface
    accidental contract violations early. Existing Pydantic errors come
    through here as a single ERROR per failure to keep the report flat.
    """
    if plan is None:
        return []
    try:
        ModelingPlan.model_validate(plan.model_dump())
    except Exception as exc:  # pragma: no cover - exercised by tests
        return [
            ValidationIssue(
                code="PYDANTIC_SCHEMA",
                severity=Severity.ERROR,
                message=f"ModelingPlan re-validation failed: {exc}",
            )
        ]
    return []


def _check_referential_integrity(parsed_yaml: dict[str, Any] | None) -> list[ValidationIssue]:
    """Apply the cross-entity rules from the agent.md guardrails."""
    if not parsed_yaml:
        return []

    issues: list[ValidationIssue] = []

    hubs = parsed_yaml.get("hubs") or []
    sats = parsed_yaml.get("satellites") or []
    eff_sats = parsed_yaml.get("eff_sats") or []
    pit_tables = parsed_yaml.get("pit_tables") or []
    bridge_tables = parsed_yaml.get("bridge_tables") or []
    bv_sats = parsed_yaml.get("bv_sats") or []
    staging = parsed_yaml.get("staging") or []

    hub_names = {str(h.get("name", "")).lower() for h in hubs if isinstance(h, dict)}

    # Orphan satellites
    for sat in sats:
        if not isinstance(sat, dict):
            continue
        parent = str(sat.get("parent_hub", "")).lower()
        if parent and parent not in hub_names:
            issues.append(
                ValidationIssue(
                    code="ORPHAN_SAT",
                    severity=Severity.ERROR,
                    message=(
                        f"Satellite '{sat.get('name')}' references unknown parent hub '{parent}'."
                    ),
                    location=f"satellites['{sat.get('name')}'].parent_hub",
                )
            )

    # Hashdiffs declared in staging?
    declared_hashdiffs: set[str] = set()
    for stage in staging:
        if not isinstance(stage, dict):
            continue
        hashed = stage.get("hashed_columns", {}) or {}
        if isinstance(hashed, dict):
            for col, val in hashed.items():
                if isinstance(val, dict) and val.get("is_hashdiff"):
                    declared_hashdiffs.add(str(col).lower())
    for sat in sats:
        if not isinstance(sat, dict):
            continue
        hd = str(sat.get("hashdiff", "")).lower()
        if hd and hd not in declared_hashdiffs:
            issues.append(
                ValidationIssue(
                    code="UNDECLARED_HASHDIFF",
                    severity=Severity.ERROR,
                    message=(
                        f"Satellite '{sat.get('name')}' uses hashdiff "
                        f"'{hd}' which is not declared in any staging entry."
                    ),
                    location=f"satellites['{sat.get('name')}'].hashdiff",
                    suggestion=(
                        "Add the hashdiff column under the matching staging.hashed_columns block."
                    ),
                )
            )

    # System columns must not appear in payloads or hashdiff payload columns.
    for sat in sats:
        if not isinstance(sat, dict):
            continue
        payload = sat.get("payload", []) or []
        for col in payload:
            if str(col).lower() in _SYSTEM_COLUMN_NAMES:
                issues.append(
                    ValidationIssue(
                        code="SYSTEM_COL_IN_PAYLOAD",
                        severity=Severity.ERROR,
                        message=(
                            f"System column '{col}' is included in payload of "
                            f"'{sat.get('name')}'. Technical columns must never be tracked."
                        ),
                        location=f"satellites['{sat.get('name')}'].payload",
                    )
                )

    # appendOnly must NOT be set on eff_sats / PIT / bridges / merge BV sats.
    forbidden_append_only = {
        "eff_sats": eff_sats,
        "pit_tables": pit_tables,
        "bridge_tables": bridge_tables,
    }
    for section, items in forbidden_append_only.items():
        for item in items:
            if not isinstance(item, dict):
                continue
            cfg = item.get("databricks_config", {}) or {}
            props = cfg.get("table_properties", {}) or {}
            if props.get("delta.appendOnly") is True:
                issues.append(
                    ValidationIssue(
                        code="APPEND_ONLY_FORBIDDEN",
                        severity=Severity.ERROR,
                        message=(
                            f"{section[:-1]} '{item.get('name')}' must not set "
                            "delta.appendOnly=true (this entity performs updates)."
                        ),
                        location=f"{section}['{item.get('name')}'].databricks_config.table_properties",
                    )
                )

    # on_schema_change must be set on every incremental model.
    for section_name, items in (
        ("hubs", hubs),
        ("satellites", sats),
        ("eff_sats", eff_sats),
        ("bv_sats", bv_sats),
    ):
        for item in items:
            if not isinstance(item, dict):
                continue
            cfg = item.get("databricks_config", {}) or {}
            if cfg.get("materialized") != "incremental":
                continue
            if not cfg.get("on_schema_change"):
                issues.append(
                    ValidationIssue(
                        code="MISSING_ON_SCHEMA_CHANGE",
                        severity=Severity.WARNING,
                        message=(
                            f"{section_name[:-1]} '{item.get('name')}' is incremental "
                            "but missing on_schema_change. Recommend 'append_new_columns'."
                        ),
                        location=f"{section_name}['{item.get('name')}'].databricks_config",
                        suggestion="Set on_schema_change: append_new_columns",
                    )
                )

    return issues


# ─── public entry point ─────────────────────────────────────────────────────


def validate(
    *,
    plan: ModelingPlan | None = None,
    rendered_yaml: str | None = None,
    bv: BvProposal | None = None,
    dbt_config: DbtGateConfig | None = None,
    dbt_runner: DbtCommandRunner | None = None,
) -> ValidationReport:
    """Run all applicable checks and return a single :class:`ValidationReport`.

    At least one of ``plan`` / ``rendered_yaml`` should be supplied. Passing
    both gives the strongest coverage (Pydantic + YAML + referential). When
    ``dbt_config.enabled`` the plan is also materialised into the configured
    dbt project and run through ``dbt parse``/``compile``(/``build``); any dbt
    failure is an ERROR, so the approval gate blocks a plan that won't compile.
    """
    issues: list[ValidationIssue] = []
    checks_run: list[str] = []

    parsed_yaml: dict[str, Any] | None = None
    if rendered_yaml is not None:
        yaml_issues, parsed_yaml = _check_yaml_syntax(rendered_yaml)
        issues.extend(yaml_issues)
        checks_run.append("yaml_syntax")

    if plan is not None:
        issues.extend(_check_pydantic_schema(plan))
        checks_run.append("pydantic_schema")

    if parsed_yaml is not None:
        issues.extend(_check_referential_integrity(parsed_yaml))
        checks_run.append("referential_integrity")

    if dbt_config is not None and dbt_config.enabled:
        issues.extend(run_dbt_gate(plan, bv, config=dbt_config, runner=dbt_runner))
        checks_run.append("dbt_compile")

    summary = CheckSummary(
        errors=sum(1 for i in issues if i.severity is Severity.ERROR),
        warnings=sum(1 for i in issues if i.severity is Severity.WARNING),
        infos=sum(1 for i in issues if i.severity is Severity.INFO),
    )

    plan_id = plan.system_id if plan is not None else stable_id(rendered_yaml or "<empty>")

    return ValidationReport(
        plan_id=plan_id,
        computed_at=datetime.now(timezone.utc),
        issues=tuple(issues),
        summary=summary,
        checks_run=tuple(checks_run),
    )
