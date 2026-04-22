"""
Hub component for Data Vault v2.
"""

from logging import Logger

from src.dv_components.components.base import DVBaseRawVaultComponent
from src.dv_components.pydantic_model.sql.raw_vaul import HubModel


class HubComponent(DVBaseRawVaultComponent):
    """Data Vault Hub component."""

    def __init__(self, model: HubModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model, HubModel):
            raise ValueError(f"Expected HubModel, got {type(model)}")
        self.model: HubModel = model

    def _get_render_kwargs(self) -> dict:
        return dict(
            config_options=self._build_sql_config({"unique_key": self.model.src_pk}),
            source_model=self._formatter.format_list(self.model.source_model),
            src_pk=self.model.src_pk,
            src_nk=self.model.src_nk,
            src_ldts=self.model.src_ldts,
            src_source=self.model.src_source,
        )

    @property
    def _sql_template_body(self) -> str:
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

    @property
    def _cols_for_yml(self) -> list[dict]:
        return self._default_cols_for_yml


if __name__ == "__main__":
    from shared.logger.default_logger import default_logger

    model = meta = HubModel(
        name="Terminal",
        source_model=["stg_terminals"],
        src_pk="HK_TERMINAL",
        src_nk="mrid",
        src_ldts="LOAD_DATE",
        src_source="RECORD_SOURCE",
    )
    hub = HubComponent(model=model, logger=default_logger)
    sql = hub.generate_sql_str()
