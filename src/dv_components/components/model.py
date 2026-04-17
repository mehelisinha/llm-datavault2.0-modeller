from typing import Annotated, Any, List, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class DvBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    source_model: list[str]
    src_source: str = "RECORD_SOURCE"
    schema_name: str = Field(default="raw_vault", alias="schema")


class RawVaultBaseModel(DvBaseModel):
    src_pk: str
    src_ldts: str


class HubModel(RawVaultBaseModel):
    dv_type: Literal["hub"] = "hub"
    layer: Literal["raw_vault"] = "raw_vault"
    src_nk: str


class LinkModel(RawVaultBaseModel):
    dv_type: Literal["link"] = "link"
    layer: Literal["raw_vault"] = "raw_vault"
    src_fk: list[str]


class SatelliteBaseModel(RawVaultBaseModel):
    layer: Literal["raw_vault"] = "raw_vault"
    src_eff: str | None = None


class SatelliteModel(SatelliteBaseModel):
    dv_type: Literal["satellite"] = "satellite"
    src_hashdiff: str
    src_payload: list[str]


class EffSatModel(SatelliteBaseModel):
    dv_type: Literal["eff_sat"] = "eff_sat"
    src_dfk: str
    src_sfk: str | list[str]  # required by automate_dv — single FK or list for higher-order links
    src_end_date: str          # required by automate_dv — column marking end of effectivity


# -----------STAGING-----------------------------


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
    def validate_expr_or_source(self):
        if self.expr and self.source_column:
            raise ValueError("Provide either 'expr' or 'source_column', not both")
        if not self.expr and not self.source_column:
            raise ValueError("Either 'expr' or 'source_column' must be provided")
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


class StagingModel(DvBaseModel):
    dv_type: Literal["staging"] = "staging"
    layer: Literal["staging"] = "staging"
    include_source_columns: bool = True
    source_model: list[str]
    source_name: str | None = None  # dbt source name (e.g. "bronze"); when set, uses {{ source() }} ref
    derived_columns: list[DerivedColumnInternal] = Field(default_factory=list)
    hashed_columns: list[HashedColumns] = Field(default_factory=list)
    null_columns: list[NullColumns] = Field(default_factory=list)
    ranked_columns: list[RankedColumns] = Field(default_factory=list)

    @computed_field
    @property
    def _null_columns_dv(self) -> dict[str, list[str]] | None:
        if self.null_columns:
            return {
                "required": [c.column_name for c in self.null_columns if c.is_required],
                "optional": [
                    c.column_name for c in self.null_columns if not c.is_required
                ],
            }
        return None

    def _get_dv_dict(self, field_name: str) -> dict[str, Any] | None:
        value = getattr(self, field_name, None)

        if not value or not isinstance(value, list):
            return None

        first = value[0]

        if isinstance(first, BaseModel) and hasattr(first, "dv_model"):
            result: dict[str, Any] = {}
            for val in value:
                result.update(val.dv_model)
            return result

        return None

    def get_dv_from_field(self, field_name: str) -> dict[str, Any] | None:
        if field_name == "null_columns":
            return self._null_columns_dv
        if field_name in ["derived_columns", "hashed_columns", "ranked_columns"]:
            return self._get_dv_dict(field_name)
        return getattr(self, field_name, None)

    # def get_dv_list(self, field_name: str) -> list[dict[str, Any]] | None:
    #     value = getattr(self, field_name, None)

    #     if not value:
    #         return None

    #     # ensure it's a list
    #     if not isinstance(value, list):
    #         return None

    #     # check if elements are pydantic models
    #     if len(value) == 0:
    #         return None

    #     first = value[0]

    #     # Pydantic v2
    #     if hasattr(first, "model_dump"):
    #         return [v.model_dump() for v in value]

    #     # fallback for plain dicts
    #     if isinstance(first, dict):
    #         return value

    #     return None

    # @computed_field
    # @property
    # def derived_columns_dv(self) -> dict[str, Any] | None:
    #     return (
    #         {k: v for c in self.derived_columns for k, v in c.dv_dict.items()}
    #         if self.derived_columns
    #         else None
    #     )

    # @computed_field
    # @property
    # def ranked_columns_dv(self) -> dict[str, Any] | None:
    #     return (
    #         {k: v for c in self.ranked_columns for k, v in c.dv_dict.items()}
    #         if self.derived_columns
    #         else None
    #     )


class DVProjectModel(BaseModel):
    dv_type: Literal["dv_project"] = "dv_project"
    system: str
    profile: str
    model_paths: list[str]
    analysis_paths: List[str] | None = None
    test_paths: List[str] | None = None
    seed_paths: List[str] | None = None
    macro_paths: List[str] | None = None
    snapshot_paths: List[str] | None = None
    target_path: str = "target"
    clean_targets: List[str] | None = None
    vars: dict[str, Any] = Field(default_factory=dict)
    catalog: str | None = None
    stg_schema: str
    raw_vault_schema: str
    business_vault_schema: str | None


class DbtPackage(BaseModel):
    package: str
    version: str


class DVPackagesModel(BaseModel):
    packages: list[DbtPackage] = Field(
        default_factory=lambda: [
            DbtPackage(package="dbt-labs/dbt_utils", version="1.3.3"),
            DbtPackage(package="metaplane/dbt_expectations", version="0.10.10"),
            DbtPackage(package="Datavault-UK/automate_dv", version="0.10.2"),
        ]
    )


DvModels = Annotated[
    Union[HubModel, LinkModel, SatelliteModel, EffSatModel, DVProjectModel, StagingModel],
    Field(discriminator="dv_type"),
]


class DVComponentModel(BaseModel):
    name: str
    description: str | None = None
    meta: DvModels

    @property
    def dv_type(self) -> str:
        return self.meta.dv_type

    @model_validator(mode="after")
    def set_description(self):
        if not self.description:
            self.description = f"Data Vault {self.dv_type} for {self.name}"
        return self

    @computed_field
    @property
    def base_models_path(self) -> str | None:
        if self.dv_type == "dv_project":
            return None
        if self.dv_type == "staging":
            return "models/staging"
        if hasattr(self.meta, "layer") and self.meta.layer is not None:
            return f"models/{self.meta.layer}/{self.dv_type}s"
        return "models"
