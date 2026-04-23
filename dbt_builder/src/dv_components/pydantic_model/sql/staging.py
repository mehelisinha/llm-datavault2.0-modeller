from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    computed_field,
    model_validator,
)

from dbt_builder.src.dv_components.pydantic_model.enums import DBTModelNames, DbtPaths
from dbt_builder.src.dv_components.pydantic_model.sql.base import DvBaseSqlModel

# ── Staging model ─────────────────────────────────────────────────────────────


class HashedColumns(BaseModel):
    column_name: str
    is_hashdiff: bool
    columns: list[str]

    @computed_field
    @property
    def dv_model(self) -> dict[str, dict[str, list[str] | bool]]:
        return {
            self.column_name: {"is_hashdiff": self.is_hashdiff, "columns": self.columns}
        }


class DerivedColumn(BaseModel):
    column_name: str
    expr: str | None = None
    source_column: str | list[str] | None = None
    escape: bool = False

    @model_validator(mode="after")
    def _expr_xor_source(self) -> DerivedColumn:
        if self.expr and self.source_column:
            raise ValueError("Provide either 'expr' or 'source_column', not both.")
        if not self.expr and not self.source_column:
            raise ValueError("Either 'expr' or 'source_column' must be provided.")
        return self

    @computed_field
    @property
    def dv_model(self) -> dict[str, Any]:
        if self.expr:
            return {self.column_name: self.expr}
        return {
            self.column_name: {
                "source_column": self.source_column,
                "escape": self.escape,
            }
        }


class DerivedColumnInternal(DerivedColumn):
    order: int


class RankedColumns(BaseModel):
    column_name: str
    partition_by: str
    order_by: str
    dense_rank: bool = False

    @computed_field
    @property
    def dv_model(self) -> dict[str, dict[str, str | bool]]:
        return {
            self.column_name: {
                "partition_by": self.partition_by,
                "order_by": self.order_by,
                "dense_rank": self.dense_rank,
            }
        }


class NullColumns(BaseModel):
    column_name: str
    is_required: bool = True


class StagingModel(DvBaseSqlModel):
    dv_type: Literal["staging"] = DBTModelNames.STAGING  # type: ignore
    layer: Literal["STG"] = "STG"
    include_source_columns: bool = True
    source_name: str | None = Field(
        default=None,
        description="dbt source name (e.g. 'bronze'); when set, uses {{ source() }} ref",
    )
    derived_columns: list[DerivedColumnInternal] = Field(default_factory=list)
    hashed_columns: list[HashedColumns] = Field(default_factory=list)
    null_columns: list[NullColumns] = Field(default_factory=list)
    ranked_columns: list[RankedColumns] = Field(default_factory=list)

    @property
    def models_path(self) -> str:
        return DbtPaths.STAGING

    @computed_field
    @property
    def _null_columns_dv(self) -> dict[str, list[str]] | None:
        if not self.null_columns:
            return None
        return {
            "required": [c.column_name for c in self.null_columns if c.is_required],
            "optional": [c.column_name for c in self.null_columns if not c.is_required],
        }

    def _get_dv_dict(self, field_name: str) -> dict[str, Any] | None:
        items = getattr(self, field_name, None)
        if not items or not isinstance(items, list):
            return None
        first = items[0]
        if isinstance(first, BaseModel) and hasattr(first, "dv_model"):
            result: dict[str, Any] = {}
            for item in items:
                result.update(item.dv_model)
            return result
        return None

    def get_dv_from_field(self, field_name: str) -> dict[str, Any] | None:
        if field_name == "null_columns":
            return self._null_columns_dv
        if field_name in ("derived_columns", "hashed_columns", "ranked_columns"):
            return self._get_dv_dict(field_name)
        return getattr(self, field_name, None)
