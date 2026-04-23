from __future__ import annotations

# ── Project-level / config models (no dbt file output) ───────────────────────
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from dbt_builder.src.dv_components.pydantic_model.base import DVBaseModel
from dbt_builder.src.dv_components.pydantic_model.enums import DBTModelNames, DbtPaths


class DVYMLModel(DVBaseModel):
    layer: Literal["PRJ"] = "PRJ"

    @property
    def file_extension(self) -> list[Literal["sql", "yml"]]:
        return ["yml"]


# -------PROJECT ---------------------------------------------------------------------
class DVProjectModel(DVYMLModel):
    name: str
    dv_type: Literal["project"] = "project"
    profile: str
    model_paths: list[str] = Field(default_factory=lambda: [DbtPaths.MODELS])
    analysis_paths: list[str] | None = Field(
        default_factory=lambda: [DbtPaths.ANALYSES]
    )
    test_paths: list[str] | None = Field(default_factory=lambda: [DbtPaths.TESTS])
    seed_paths: list[str] | None = Field(default_factory=lambda: [DbtPaths.SEEDS])
    macro_paths: list[str] | None = Field(default_factory=lambda: [DbtPaths.MACROS])
    snapshot_paths: list[str] | None = Field(
        default_factory=lambda: [DbtPaths.SNAPSHOTS]
    )
    target_path: str = Field(default_factory=lambda: DbtPaths.TARGET)
    clean_targets: list[str] | None = Field(
        default_factory=lambda: [DbtPaths.TARGET, DbtPaths.DBT_PACKAGES]
    )
    vars: dict[str, Any] = Field(default_factory=dict)
    catalog: str | None = None
    stg_schema: str
    raw_vault_schema: str
    business_vault_schema: str | None

    @property
    def file_name(self) -> str:
        return f"{DBTModelNames.PROJECT}"

    @property
    def models_path(self) -> None:
        return None


# -------PACKAGES ---------------------------------------------------------------------
class DbtPackage(BaseModel):
    package: str
    version: str


class DVPackagesModel(DVYMLModel):
    """Not part of DvModels — instantiated directly, not via DVComponentModel."""

    dv_type: Literal["packages"] = "packages"
    packages: list[DbtPackage] = Field(
        default_factory=lambda: [
            DbtPackage(package="dbt-labs/dbt_utils", version="1.3.3"),
            DbtPackage(package="metaplane/dbt_expectations", version="0.10.10"),
            DbtPackage(package="Datavault-UK/automate_dv", version="0.11.1"),
        ]
    )

    @property
    def models_path(self) -> None:
        return None

    @property
    def file_name(self) -> str:
        return f"{DBTModelNames.PACKAGES}"


# -------SOURCES§ ---------------------------------------------------------------------
class TableConfig(BaseModel):
    name: str


class DvSourceModel(DVYMLModel):
    dv_type: Literal["sources"] = (
        "sources"  # was "sources" — made singular for consistency
    )
    name: str
    database: str
    schema_name: str = Field(..., alias="schema")
    tables: list[TableConfig]

    @property
    def models_path(self) -> str:
        return DbtPaths.STAGING

    @property
    def file_name(self) -> str:
        return f"{DBTModelNames.SOURCES}"


# -------PROFILES ---------------------------------------------------------------------
class DVProfileComputeWarehouse(BaseModel):
    http_path: str


class DVProfileOutputModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["databricks"] = "databricks"
    catalog: str
    schema_name: str = Field(..., alias="schema")
    host: str = "{{ env_var('DBT_DATABRICKS_HOST') }}"
    http_path: str = "{{ env_var('DBT_DATABRICKS_HTTP_PATH') }}"
    method: str = "http"
    token: str = "{{ env_var('DBT_DATABRICKS_TOKEN') }}"
    threads: int = 1
    compute: dict[str, DVProfileComputeWarehouse] | None = None


class DvProfilesModel(DVYMLModel):
    dv_type: Literal["profiles"] = "profiles"
    name: str
    target: str = "dev"
    outputs: dict[str, DVProfileOutputModel]

    @model_validator(mode="after")
    def _target_exists(self) -> DvProfilesModel:
        if self.target not in self.outputs:
            raise ValueError(
                f"Target '{self.target}' must exist in outputs: {list(self.outputs)}"
            )
        return self

    @property
    def models_path(self) -> None:
        return None

    @property
    def file_name(self) -> str:
        return f"{DBTModelNames.PROFILES}"
