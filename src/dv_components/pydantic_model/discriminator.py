# models.py
from __future__ import annotations

from typing import Annotated, Union

from pydantic import (
    Field,
)

from src.dv_components.pydantic_model.proj_level.dv_yml import (
    DVPackagesModel,
    DvProfilesModel,
    DVProjectModel,
    DvSourceModel,
)
from src.dv_components.pydantic_model.sql.macro import (
    MacroModel,
)
from src.dv_components.pydantic_model.sql.raw_vaul import (
    EffSatModel,
    HubModel,
    LinkModel,
    SatelliteModel,
)
from src.dv_components.pydantic_model.sql.staging import StagingModel

## ── Discriminated unions ──────────────────────────────────────────────────────

SqlModels = Annotated[
    Union[HubModel, LinkModel, SatelliteModel, EffSatModel, StagingModel, MacroModel],
    Field(discriminator="dv_type"),
]

ProjectModels = Annotated[
    Union[DVProjectModel, DvSourceModel, DvProfilesModel, DVPackagesModel],
    Field(discriminator="dv_type"),
]

DvModels = Annotated[
    Union[
        # SQL Models
        HubModel,
        LinkModel,
        SatelliteModel,
        EffSatModel,
        StagingModel,
        MacroModel,
        # Project Models
        DVProjectModel,
        DvSourceModel,
        DvProfilesModel,
        DVPackagesModel,
    ],
    Field(discriminator="dv_type"),
]


# ── Top-level component wrapper ───────────────────────────────────────────────


# class DVComponentModel(BaseModel):
# #     name: str
# #     description: str | None = None
# #     meta: DvModels

# #     @property
# #     def dv_type(self) -> str:
# #         return self.meta.dv_type

# #     @model_validator(mode="after")
# #     def _default_description(self) -> DVComponentModel:
# #         if not self.description:
# #             self.description = f"Data Vault {self.dv_type} for {self.name}"
# #         return self

# #     @computed_field
# #     @property
# #     def base_models_path(self) -> str | None:
# #         return self.meta.models_path
