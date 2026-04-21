from typing import Annotated, Any, List, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class MacroModel(BaseModel):
    dv_type: Literal["macro"] = "macro"
    layer: Literal["macro"] = "macro"


class DvBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    source_model: list[str]
    src_source: str = "RECORD_SOURCE"
    schema_name: str = Field(default="raw_vault", alias="schema")


class RawVaultBaseModel(DvBaseModel):
    src_pk: str
    src_ldts: str
    layer: Literal["raw_vault"] = "raw_vault"


class HubModel(RawVaultBaseModel):
    dv_type: Literal["hub"] = "hub"
    src_nk: str


class LinkModel(RawVaultBaseModel):
    dv_type: Literal["link"] = "link"
    src_fk: list[str]


class SatelliteBaseModel(RawVaultBaseModel):
    """
    A base model for Satellite entities in a Raw Vault data warehouse.

    This model represents a Satellite table which stores descriptive attributes and their changes
    over time for a core business entity (Hub). Satellites maintain a complete history of attribute
    changes with effectivity dating.

    Attributes:
        layer (Literal["raw_vault"]): The data warehouse layer designation. Always set to "raw_vault"
            for raw vault entities.
        src_eff (str | None): An effectivity date. Usually called EFFECTIVE_FROM, this column is the
            business effective date of a Satellite record. It records that a record is valid from a
            specific point in time. If a customer changes their name, then the record with their 'old'
            name should no longer be valid, and it will no longer have the most recent EFFECTIVE_FROM value.

    Raises:
        ValueError: If more than one source_model is provided, as a Satellite can only have a single
            source model.
    """

    layer: Literal["raw_vault"] = "raw_vault"
    src_eff: str | None = Field(
        default=None, description="Business effective date column (e.g. __inserted_at)"
    )

    @model_validator(mode="after")
    def validate_expr_or_source(self):
        if len(self.source_model) > 1:
            raise ValueError("EffSatModel can have only 1 source_model")
        return self


class SatelliteModel(SatelliteBaseModel):
    dv_type: Literal["satellite"] = "satellite"
    src_hashdiff: str
    src_payload: list[str]


class EffSatModel(SatelliteBaseModel):
    dv_type: Literal["eff_sat"] = "eff_sat"
    src_dfk: str
    src_sfk: (
        str | list[str]
    )  # required by automate_dv — single FK or list for higher-order links
    src_end_date: str = Field(description="Column marking end of effectivity")
    src_start_date: str = Field(
        description="It records that a record is valid from a specific point in time"
    )


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
    source_name: str | None = (
        None  # dbt source name (e.g. "bronze"); when set, uses {{ source() }} ref
    )
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


# -----------PROJECT-----------------------------
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


# -----------PACKAGE-----------------------------
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


class TableConfig(BaseModel):
    name: str


# -----------Sourcses-----------------------------
class DVSourceModel(BaseModel):
    dv_type: Literal["sources"] = "sources"
    name: str
    database: str
    schema_name: str = Field(..., alias="schema")
    tables: List[TableConfig]


# -----------Profiles-----------------------------


class DVProfileComputeWarehouse(BaseModel):
    http_path: str


class DVProfileOutputModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["databricks"] = "databricks"
    catalog: str
    schema_name: str = Field(..., alias="schema")
    host: str
    http_path: str
    method: str = "http"
    token: str
    threads: int = 1
    compute: dict[str, DVProfileComputeWarehouse] | None = None


class DVProfileModel(BaseModel):
    dv_type: Literal["profiles"] = "profiles"
    name: str
    target: str = "dev"
    outputs: dict[str, DVProfileOutputModel]

    @model_validator(mode="after")
    def validate_target_exists(self):
        if self.target not in self.outputs:
            raise ValueError(
                f"Target '{self.target}' must exist in profile outputs: {list(self.outputs)}"
            )
        return self

    @computed_field
    @property
    def dv_model(self) -> dict[str, Any]:
        return {
            self.name: {
                "target": self.target,
                "outputs": {
                    key: value.model_dump(by_alias=True, exclude_none=True)
                    for key, value in self.outputs.items()
                },
            }
        }


DvModels = Annotated[
    Union[
        HubModel,
        LinkModel,
        SatelliteModel,
        EffSatModel,
        DVProjectModel,
        StagingModel,
        MacroModel,
        DVSourceModel,
    ],
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
        layer = getattr(self.meta, "layer", None)
        if layer is not None:
            return f"models/{layer}/{self.dv_type}s"
        return "models"
