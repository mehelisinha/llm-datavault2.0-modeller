# models.py
from __future__ import annotations

from typing import Annotated, Union

from pydantic import (
    Field,
)

from dbt_builder.src.dv_components.pydantic_model.proj_level.dv_yml import (
    DVPackagesModel,
    DvProfilesModel,
    DVProjectModel,
    DvSourceModel,
)
from dbt_builder.src.dv_components.pydantic_model.sql.business_vault import (
    BridgeModel,
    BvSatModel,
    DimModel,
    FactModel,
    PitModel,
)
from dbt_builder.src.dv_components.pydantic_model.sql.macro import (
    MacroModel,
)
from dbt_builder.src.dv_components.pydantic_model.sql.raw_vaul import (
    EffSatModel,
    HubModel,
    LinkModel,
    SatelliteModel,
)
from dbt_builder.src.dv_components.pydantic_model.sql.staging import StagingModel

## ── Discriminated unions ──────────────────────────────────────────────────────

SqlModels = Annotated[
    Union[HubModel, LinkModel, SatelliteModel, EffSatModel, StagingModel, MacroModel],
    Field(discriminator="dv_type"),
]

ProjectModels = Annotated[
    Union[DVProjectModel, DvSourceModel, DvProfilesModel, DVPackagesModel],
    Field(discriminator="dv_type"),
]

BvModels = Annotated[
    Union[PitModel, BridgeModel, DimModel, FactModel, BvSatModel],
    Field(discriminator="dv_type"),
]

DvModels = Annotated[
    Union[
        # SQL / Raw Vault Models
        HubModel,
        LinkModel,
        SatelliteModel,
        EffSatModel,
        StagingModel,
        MacroModel,
        # Business Vault Models
        PitModel,
        BridgeModel,
        DimModel,
        FactModel,
        BvSatModel,
        # Project Models
        DVProjectModel,
        DvSourceModel,
        DvProfilesModel,
        DVPackagesModel,
    ],
    Field(discriminator="dv_type"),
]
