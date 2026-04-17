"""
Satellite components for Data Vault v2.

Contains:
- SatelliteBase: abstract base for both satellite flavors
- Satellite:     regular satellite (src_hashdiff + src_payload)
- EffSat:        effectivity satellite (src_dfk + src_eff, tracks relationship lifecycle)
- SatelliteFactory: creates the right flavor based on model type
"""

from abc import abstractmethod
from logging import Logger

from src.dv_components.models.base import DVBaseRawVaultComponent
from src.dv_components.models.model import (
    DVComponentModel,
    EffSatModel,
    SatelliteModel,
)


class SatelliteBase(DVBaseRawVaultComponent):
    """Abstract base for all satellite component flavors."""

    @abstractmethod
    def _get_render_kwargs(self) -> dict: ...

    @property
    @abstractmethod
    def _template_body(self) -> str: ...


class Satellite(SatelliteBase):
    """Regular Data Vault Satellite (descriptive attributes with hashdiff)."""

    def __init__(self, model: DVComponentModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model.meta, SatelliteModel):
            raise ValueError(f"Expected SatelliteModel, got {type(model.meta)}")
        self.satellite_model: SatelliteModel = model.meta

    def _get_render_kwargs(self) -> dict:
        return dict(
            config_options=self._build_config(
                {
                    "unique_key": [
                        self.satellite_model.src_pk,
                        self.satellite_model.src_ldts,
                    ]
                }
            ),
            source_model=self._formatter.format_list(self.satellite_model.source_model),
            src_pk=self.satellite_model.src_pk,
            src_hashdiff=self.satellite_model.src_hashdiff,
            src_payload=self._formatter.format_list(self.satellite_model.src_payload),
            src_ldts=self.satellite_model.src_ldts,
            src_source=self.satellite_model.src_source,
            src_eff=self.satellite_model.src_eff,
        )

    @property
    def _template_body(self) -> str:
        return """
<% set rendered = render_config(config_options) %>
<<rendered>>
{%- set source_model = <<source_model>> -%}
{%- set src_pk       = '<<src_pk>>' -%}
{%- set src_hashdiff = '<<src_hashdiff>>' -%}
{%- set src_payload  = <<src_payload>> -%}
{%- set src_ldts     = '<<src_ldts>>' -%}
{%- set src_source   = '<<src_source>>' -%}
<% if src_eff %>{%- set src_eff      = '<<src_eff>>' -%}
<% endif %>{{ automate_dv.sat(
    src_pk      = src_pk,
    src_hashdiff= src_hashdiff,
    src_payload = src_payload,
    src_ldts    = src_ldts,
    src_source  = src_source,<% if src_eff %>
    src_eff     = src_eff,<% endif %>
    source_model= source_model
) }}"""


class EffSat(SatelliteBase):
    """Effectivity Satellite — tracks relationship lifecycle (open/close via CDC)."""

    def __init__(self, model: DVComponentModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model.meta, EffSatModel):
            raise ValueError(f"Expected EffSatModel, got {type(model.meta)}")
        self.eff_sat_model: EffSatModel = model.meta

    def _get_render_kwargs(self) -> dict:
        sfk = self.eff_sat_model.src_sfk
        # Render as a Jinja list literal for multi-FK links, or a quoted string for single FK
        src_sfk_rendered = (
            self._formatter.format_list(sfk) if isinstance(sfk, list) else f"'{sfk}'"
        )
        return dict(
            config_options=self._build_config(
                {"unique_key": [self.eff_sat_model.src_pk, self.eff_sat_model.src_ldts]}
            ),
            source_model=self._formatter.format_list(self.eff_sat_model.source_model),
            src_pk=self.eff_sat_model.src_pk,
            src_dfk=self.eff_sat_model.src_dfk,
            src_sfk=src_sfk_rendered,
            src_eff=self.eff_sat_model.src_eff,
            src_end_date=self.eff_sat_model.src_end_date,
            src_ldts=self.eff_sat_model.src_ldts,
            src_source=self.eff_sat_model.src_source,
        )

    @property
    def _template_body(self) -> str:
        return """
<% set rendered = render_config(config_options) %>
<<rendered>>
{%- set source_model = <<source_model>> -%}
{%- set src_pk       = '<<src_pk>>' -%}
{%- set src_dfk      = '<<src_dfk>>' -%}
{%- set src_sfk      = <<src_sfk>> -%}
{%- set src_eff      = '<<src_eff>>' -%}
{%- set src_end_date = '<<src_end_date>>' -%}
{%- set src_ldts     = '<<src_ldts>>' -%}
{%- set src_source   = '<<src_source>>' -%}
{{ automate_dv.eff_sat(
    src_pk         = src_pk,
    src_dfk        = src_dfk,
    src_sfk        = src_sfk,
    src_start_date = src_eff,
    src_end_date   = src_end_date,
    src_eff        = src_eff,
    src_ldts       = src_ldts,
    src_source     = src_source,
    source_model   = source_model
) }}"""


class SatelliteFactory:
    """Returns the correct satellite component based on the model's dv_type."""

    def __new__(cls, model: DVComponentModel, logger: Logger) -> SatelliteBase:
        if isinstance(model.meta, EffSatModel):
            return EffSat(model=model, logger=logger)
        return Satellite(model=model, logger=logger)


if __name__ == "__main__":
    from shared.logger.default_logger import default_logger

    # --- Regular Satellite ---
    sat_model = SatelliteModel(
        source_model=["stg_terminals"],
        src_pk="HK_TERMINAL",
        src_hashdiff="HASHDIFF_TERMINAL_DETAILS",
        src_payload=["name", "sequence_number"],
        src_ldts="LOAD_DATE",
        src_eff="EFFECTIVE_FROM",
    )
    model = DVComponentModel(name="sat_terminal_details", meta=sat_model)
    sat = SatelliteFactory(model=model, logger=default_logger)
    print(sat.generate())

    # --- Effectivity Satellite ---
    eff_model = EffSatModel(
        source_model=["stg_terminals"],
        src_pk="HK_TERMINAL_EQUIPMENT_NODE",
        src_dfk="HK_TERMINAL_EQUIPMENT_NODE",
        src_eff="EFFECTIVE_FROM",
        src_ldts="LOAD_DATE",
    )
    model = DVComponentModel(name="eff_sat_terminal_equipment_node", meta=eff_model)
    eff = SatelliteFactory(model=model, logger=default_logger)
    print(eff.generate())
