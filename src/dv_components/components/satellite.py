"""
Satellite component for Data Vault v2.
"""

from logging import Logger

from src.dv_components.components.base import DVBaseRawVaultComponent
from src.dv_components.components.model import DVComponentModel, SatelliteModel


class Satellite(DVBaseRawVaultComponent):
    """Data Vault Satellite component."""

    def __init__(self, model: DVComponentModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model.meta, SatelliteModel):
            raise ValueError(f"Expected SatelliteModel, got {type(model.meta)}")
        self.satellite_model: SatelliteModel = model.meta

    def _get_render_kwargs(self) -> dict:
        return dict(
            config_options=self._build_config(
                {"unique_key": self.satellite_model.src_pk}
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


if __name__ == "__main__":
    from shared.logger.default_logger import default_logger

    satellite_model = SatelliteModel(
        source_model=["stg_terminals"],
        src_pk="HK_TERMINAL",
        src_hashdiff="HASHDIFF",
        src_payload=["name", "address"],
        src_ldts="LOAD_DATE",
        src_source="RECORD_SOURCE",
    )

    model = DVComponentModel(name="TERMINAL_EQUIPMENT_NODE", meta=satellite_model)
    satellite = Satellite(model=model, logger=default_logger)
    sql = satellite.generate()
