from __future__ import annotations

import re
from dataclasses import dataclass
from logging import Logger

from shared.src.logger.default_logger import default_logger
from shared.utils.spark import spark
from dbt_builder.src.runners.metadata import Metadata

_LITERAL_RE = re.compile(r"^!\{[^}]+\}$")
_SIMPLE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class StagingColumnContext:
    all_columns: set[str]
    source_columns_known: bool


class SchemaValidator:
    """Validate metadata column references against source and staging schemas."""

    def __init__(
        self,
        metadata: Metadata,
        logger: Logger = default_logger,
    ):
        self._metadata = metadata
        self._logger = logger
        self._errors: list[str] = []
        self._warnings: list[str] = []
        self._table_columns_by_source: dict[str, set[str]] = {}
        self._staging_columns_by_model: dict[str, StagingColumnContext] = {}

    def validate(self) -> None:
        self._load_source_table_columns()
        self._validate_staging_columns()
        self._validate_hubs()
        self._validate_links()
        self._validate_satellites()
        self._validate_eff_sats()

        for warning in self._warnings:
            self._logger.warning(warning)

        if self._errors:
            details = "\n- " + "\n- ".join(self._errors)
            raise ValueError(f"Schema validation failed:{details}")

        self._logger.info("Schema validation passed.")

    def _load_source_table_columns(self) -> None:
        staging_entries = self._metadata._config.get("staging", [])
        source_tables = {
            str(entry["source_table"]).strip()
            for entry in staging_entries
            if entry.get("source_table")
        }

        if not source_tables:
            return

        catalog = self._metadata.system.get("catalog")
        schema_name = self._metadata.system.get("schema")
        if not catalog or not schema_name:
            self._warnings.append(
                "Schema validator: system.catalog or system.schema missing; source "
                "table column validation is skipped."
            )
            return

        for table in source_tables:
            full_name = f"{catalog}.{schema_name}.{table}"
            try:
                rows = spark.sql(f"DESCRIBE TABLE {full_name}").collect()
            except Exception as ex:
                self._warnings.append(
                    f"Schema validator: unable to read schema for '{full_name}': {ex}"
                )
                continue

            cols = {
                str(row[0]).lower()
                for row in rows
                if row[0] and not str(row[0]).startswith("#")
            }
            self._table_columns_by_source[table] = cols

    def _validate_staging_columns(self) -> None:
        for entry in self._metadata._config.get("staging", []):
            name = str(entry.get("name", "<unnamed>"))
            source_table = str(entry.get("source_table", "")).strip()
            source_cols = self._table_columns_by_source.get(source_table, set())
            source_known = source_table in self._table_columns_by_source

            derived = entry.get("derived_columns", {}) or {}
            hashed = entry.get("hashed_columns", {}) or {}
            ranked = entry.get("ranked_columns", {}) or {}

            available = set(source_cols)

            for col_name, expr in derived.items():
                expr_text = str(expr).strip()
                if self._is_literal(expr_text):
                    pass
                elif self._is_simple_identifier(expr_text):
                    self._require_in_source(
                        source_cols,
                        source_known,
                        source_table,
                        expr_text,
                        f"staging '{name}' derived_columns.{col_name}",
                    )
                available.add(str(col_name).lower())

            for col_name, value in hashed.items():
                ref_cols = (
                    value
                    if isinstance(value, list)
                    else (value or {}).get("columns", [])
                )
                for ref in ref_cols:
                    ref_col = str(ref).strip()
                    self._reject_literal(
                        ref_col,
                        f"staging '{name}' hashed_columns.{col_name}",
                    )
                    self._require_in_available(
                        available,
                        source_known,
                        ref_col,
                        f"staging '{name}' hashed_columns.{col_name}",
                    )
                available.add(str(col_name).lower())

            for col_name, cfg in ranked.items():
                partition_expr = str((cfg or {}).get("partition_by", "")).strip()
                order_expr = str((cfg or {}).get("order_by", "")).strip()
                for expr_value, expr_field in (
                    (partition_expr, "partition_by"),
                    (order_expr, "order_by"),
                ):
                    if not expr_value:
                        continue
                    for token in self._split_expr_tokens(expr_value):
                        self._reject_literal(
                            token,
                            f"staging '{name}' ranked_columns.{col_name}.{expr_field}",
                        )
                        self._require_in_available(
                            available,
                            source_known,
                            token,
                            f"staging '{name}' ranked_columns.{col_name}.{expr_field}",
                        )
                available.add(str(col_name).lower())

            self._staging_columns_by_model[name] = StagingColumnContext(
                all_columns=available,
                source_columns_known=source_known,
            )

    def _validate_hubs(self) -> None:
        for entry in self._metadata._config.get("hubs", []):
            name = str(entry.get("name", "<unnamed>"))
            stg = str(entry.get("staging_model", "")).strip()
            self._require_stage_ref(name, stg, "hubs")
            self._require_stage_column(
                name, stg, str(entry.get("business_key", "")), "business_key"
            )
            self._require_stage_column(
                name, stg, str(entry.get("hash_key", "")), "hash_key"
            )

    def _validate_links(self) -> None:
        for entry in self._metadata._config.get("links", []):
            name = str(entry.get("name", "<unnamed>"))
            stg = str(entry.get("source_model", "")).strip()
            self._require_stage_ref(name, stg, "links")
            self._require_stage_column(
                name, stg, str(entry.get("hash_key", "")), "hash_key"
            )
            for fk in entry.get("fk_columns", []) or []:
                self._require_stage_column(name, stg, str(fk), "fk_columns")

    def _validate_satellites(self) -> None:
        for entry in self._metadata._config.get("satellites", []):
            name = str(entry.get("name", "<unnamed>"))
            stg = str(entry.get("source_model", "")).strip()
            self._require_stage_ref(name, stg, "satellites")
            self._require_stage_column(
                name, stg, str(entry.get("hash_key", "")), "hash_key"
            )
            self._require_stage_column(
                name, stg, str(entry.get("hashdiff", "")), "hashdiff"
            )
            eff_from = entry.get("effective_from")
            if eff_from:
                self._require_stage_column(name, stg, str(eff_from), "effective_from")
            for payload_col in entry.get("payload", []) or []:
                self._require_stage_column(name, stg, str(payload_col), "payload")

    def _validate_eff_sats(self) -> None:
        for entry in self._metadata._config.get("eff_sats", []):
            name = str(entry.get("name", "<unnamed>"))
            stg = str(entry.get("source_model", "")).strip()
            self._require_stage_ref(name, stg, "eff_sats")
            self._require_stage_column(
                name, stg, str(entry.get("hash_key", "")), "hash_key"
            )
            self._require_stage_column(
                name, stg, str(entry.get("driving_fk", "")), "driving_fk"
            )
            self._require_stage_column(
                name, stg, str(entry.get("effective_from", "")), "effective_from"
            )
            self._require_stage_column(
                name, stg, str(entry.get("end_date", "")), "end_date"
            )

            secondary = entry.get("secondary_fk", [])
            secondary_fks = secondary if isinstance(secondary, list) else [secondary]
            for fk in secondary_fks:
                self._require_stage_column(name, stg, str(fk), "secondary_fk")

    def _require_stage_ref(
        self, model_name: str, staging_model: str, section: str
    ) -> None:
        if staging_model in self._staging_columns_by_model:
            return
        self._errors.append(
            f"{section} '{model_name}' references unknown staging model '{staging_model}'."
        )

    def _require_stage_column(
        self,
        model_name: str,
        staging_model: str,
        col_name: str,
        field_name: str,
    ) -> None:
        ref = col_name.strip()
        if not ref:
            return

        self._reject_literal(ref, f"model '{model_name}' field '{field_name}'")

        ctx = self._staging_columns_by_model.get(staging_model)
        if not ctx:
            return

        if ref.lower() in ctx.all_columns:
            return

        if ctx.source_columns_known:
            self._errors.append(
                f"model '{model_name}' field '{field_name}' references column '{ref}' "
                f"which is not present in staging model '{staging_model}'."
            )
            return

        self._warnings.append(
            f"Schema validator: could not fully validate '{model_name}.{field_name}' "
            f"against '{staging_model}' because source table schema is unavailable."
        )

    def _require_in_source(
        self,
        source_cols: set[str],
        source_known: bool,
        source_table: str,
        col_name: str,
        context: str,
    ) -> None:
        if not source_known:
            self._warnings.append(
                f"Schema validator: source schema unavailable for table '{source_table}' "
                f"while validating {context}."
            )
            return
        if col_name.lower() not in source_cols:
            self._errors.append(
                f"{context} references source column '{col_name}' not found in table "
                f"'{source_table}'."
            )

    def _require_in_available(
        self,
        available: set[str],
        source_known: bool,
        col_name: str,
        context: str,
    ) -> None:
        if col_name.lower() in available:
            return
        if source_known:
            self._errors.append(
                f"{context} references column '{col_name}' that is not available in "
                "the staging model definition."
            )
            return
        self._warnings.append(
            f"Schema validator: could not fully validate {context} for column '{col_name}' "
            "because source schema is unavailable."
        )

    def _reject_literal(self, value: str, context: str) -> None:
        if self._is_literal(value):
            self._errors.append(
                f"{context} uses literal token '{value}', but literal tokens are only "
                "allowed in staging.derived_columns."
            )

    @staticmethod
    def _is_literal(value: str) -> bool:
        return bool(_LITERAL_RE.match(value.strip()))

    @staticmethod
    def _is_simple_identifier(value: str) -> bool:
        return bool(_SIMPLE_IDENTIFIER_RE.match(value.strip()))

    @staticmethod
    def _split_expr_tokens(expr: str) -> list[str]:
        return [token.strip() for token in expr.split(",") if token.strip()]
