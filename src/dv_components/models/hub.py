"""
Hub component for Data Vault v2.
"""

from logging import Logger

from src.dv_components.models.base import DVBaseRawVaultComponent
from src.dv_components.models.model import DVComponentModel, HubModel


class Hub(DVBaseRawVaultComponent):
    """Data Vault Hub component."""

    def __init__(self, model: DVComponentModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model.meta, HubModel):
            raise ValueError(f"Expected HubModel, got {type(model.meta)}")
        self.hub_model: HubModel = model.meta

    def _get_render_kwargs(self) -> dict:
        return dict(
            config_options=self._build_config({"unique_key": self.hub_model.src_pk}),
            source_model=self._formatter.format_list(self.hub_model.source_model),
            src_pk=self.hub_model.src_pk,
            src_nk=self.hub_model.src_nk,
            src_ldts=self.hub_model.src_ldts,
            src_source=self.hub_model.src_source,
        )

    @property
    def _template_body(self) -> str:
        return """
<% set rendered = render_config(config_options) %>
<<rendered>>
{%- set source_model = <<source_model>> -%}
{%- set src_pk       = '<<src_pk>>' -%}
{%- set src_nk       = '<<src_nk>>' -%}
{%- set src_ldts     = '<<src_ldts>>' -%}
{%- set src_source   = '<<src_source>>' -%}
{{ automate_dv.hub(
    src_pk      = src_pk,
    src_nk      = src_nk,
    src_ldts    = src_ldts,
    src_source  = src_source,
    source_model= source_model
) }}"""


if __name__ == "__main__":
    from shared.logger.default_logger import default_logger

    hub_model = meta = HubModel(
        source_model=["stg_terminals"],
        src_pk="HK_TERMINAL",
        src_nk="mrid",
        src_ldts="LOAD_DATE",
        src_source="RECORD_SOURCE",
    )

    model = DVComponentModel(name="Terminal", meta=hub_model)
    hub = Hub(model=model, logger=default_logger)
    sql = hub.generate()
