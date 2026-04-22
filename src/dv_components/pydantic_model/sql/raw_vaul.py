from __future__ import annotations

from abc import ABC
from typing import Literal

from pydantic import (
    Field,
    model_validator,
)

from src.dv_components.pydantic_model.enums import DBTModelNames, DbtPaths
from src.dv_components.pydantic_model.sql.base import DvBaseSqlModel

# ── Raw vault leaf models ─────────────────────────────────────────────────────


class RawVaultBaseModel(DvBaseSqlModel, ABC):
    dv_type: Literal["hub", "link", "satellite", "eff_sat"]
    src_pk: str
    src_ldts: str
    layer: Literal["RWV"] = "RWV"

    @property
    def models_path(self) -> str:
        return f"{DbtPaths.RAW_VAULT}/{self.dv_type}s"


class HubModel(RawVaultBaseModel):
    dv_type: Literal["hub"] = DBTModelNames.HUB  # type: ignore
    src_nk: str


class LinkModel(RawVaultBaseModel):
    dv_type: Literal["link"] = DBTModelNames.LINK  # type: ignore
    src_fk: list[str]


# ── Satellite models ──────────────────────────────────────────────────────────


class SatelliteBaseModel(RawVaultBaseModel):
    """
    Base for Satellite entities.

    Stores descriptive attributes and their changes over time for a Hub.
    Restricted to a single source model.
    """

    src_eff: str | None = Field(
        default=None,
        description="Business effective date column (e.g. EFFECTIVE_FROM)",
    )

    @model_validator(mode="after")
    def _single_source_model(self) -> SatelliteBaseModel:
        if len(self.source_model) > 1:
            raise ValueError("Satellites must have exactly one source_model.")
        return self


class SatelliteModel(SatelliteBaseModel):
    dv_type: Literal["satellite"] = DBTModelNames.SATELLITE  # type: ignore
    src_hashdiff: str
    src_payload: list[str]


class EffSatModel(SatelliteBaseModel):
    dv_type: Literal["eff_sat"] = DBTModelNames.EFF_SAT  # type: ignore
    src_dfk: str
    src_sfk: str | list[str]
    src_end_date: str = Field(description="Column marking end of effectivity")
    src_start_date: str = Field(description="Column marking start of effectivity")
