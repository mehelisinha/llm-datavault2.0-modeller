"""
Link component for Data Vault v2.
"""

from logging import Logger

from src.dv_components.models.base import DVBaseRawVaultComponent
from src.dv_components.models.model import DVComponentModel, LinkModel


class Link(DVBaseRawVaultComponent):
    """Data Vault Link component."""

    def __init__(self, model: DVComponentModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model.meta, LinkModel):
            raise ValueError(f"Expected LinkModel, got {type(model.meta)}")
        self.link_model: LinkModel = model.meta

    def _get_render_kwargs(self) -> dict:
        return dict(
            config_options=self._build_config({"unique_key": self.link_model.src_pk}),
            source_model=self._formatter.format_list(self.link_model.source_model),
            src_pk=self.link_model.src_pk,
            src_fk=self._formatter.format_list(self.link_model.src_fk),
            src_ldts=self.link_model.src_ldts,
            src_source=self.link_model.src_source,
        )

    @property
    def _template_body(self) -> str:
        return """
<% set rendered = render_config(config_options) %>
<<rendered>>
{%- set source_model = <<source_model>> -%}
{%- set src_pk       = '<<src_pk>>' -%}
{%- set src_fk       = <<src_fk>> -%}
{%- set src_ldts     = '<<src_ldts>>' -%}
{%- set src_source   = '<<src_source>>' -%}
{{ automate_dv.link(
    src_pk      = src_pk,
    src_fk      = src_fk,
    src_ldts    = src_ldts,
    src_source  = src_source,
    source_model= source_model
) }}"""


if __name__ == "__main__":
    from shared.logger.default_logger import default_logger

    link_model = LinkModel(
        source_model=["stg_terminals"],
        src_pk="HK_TERMINAL_EQUIPMENT_NODE",
        src_fk=["HK_TERMINAL", "HK_CONDUCTING_EQUIPMENT", "HK_CONNECTIVITY_NODE"],
        src_ldts="LOAD_DATE",
        src_source="RECORD_SOURCE",
    )

    model = DVComponentModel(name="TERMINAL_EQUIPMENT_NODE", meta=link_model)
    link = Link(model=model, logger=default_logger)
    sql = link.generate()
