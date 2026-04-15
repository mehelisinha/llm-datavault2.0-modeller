from typing import Annotated, Any, List, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class DvBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_models: list[str]
    src_pk: str
    src_ldts: str
    src_source: str = "RECORD_SOURCE"
    schema_name: str = Field(default="raw_vault", alias="schema")


class HubModel(DvBaseModel):
    dv_type: Literal["hub"] = "hub"
    layer: Literal["raw_vault"] = "raw_vault"
    src_nk: str


class LinkModel(DvBaseModel):
    dv_type: Literal["link"] = "link"
    layer: Literal["raw_vault"] = "raw_vault"
    src_fk: list[str]


class SatelliteModel(DvBaseModel):
    dv_type: Literal["satellite"] = "satellite"
    layer: Literal["raw_vault"] = "raw_vault"
    src_hashdiff: str
    src_payload: list[str]
    src_eff: str | None = None


class DVProjectModel(BaseModel):
    dv_type: Literal["dv_project"] = "dv_project"
    system: dict[str, str]
    name: str
    profile: str
    model_paths: list[str]
    analysis_paths: List[str]| None = None
    test_paths: List[str]|None = None
    seed_paths: List[str]|None = None
    macro_paths: List[str]|None = None
    snapshot_paths: List[str]|None = None
    target_path: str = "target"
    clean_targets: List[str]|None = None
    vars: dict[str, Any] = Field(default_factory=dict)
    stg_schema:str
    raw_vault_schema:str
    business_vault_schema:str|None


DvModels = Annotated[
    Union[HubModel, LinkModel, SatelliteModel, DVProjectModel],
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
    def base_models_path(self) -> str| None:
        if self.dv_type == "dv_project":
            return None
        if hasattr(self.meta, "layer"):
            return f"models/{self.meta.layer}/{self.dv_type}s"
        return "models"


