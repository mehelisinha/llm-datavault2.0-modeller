"""
Link component for Data Vault v2.
"""

from logging import Logger
from typing import List

from src.dv_components.components.base import DVBaseRawVaultComponent
from src.dv_components.components.model import DVComponentModel, LinkModel


class Link(DVBaseRawVaultComponent):
    """Data Vault Link component."""

    def __init__(
        self,
        model: DVComponentModel,
        source_models: List[str],
        logger:Logger
    ):
        super().__init__(model=model, source_models=source_models, logger=logger)

        if not isinstance(model.meta, LinkModel):
            raise ValueError(f"Expected LinkModel, got {type(model.meta)}")
        self.link_model: LinkModel = model.meta

    def generate(self) -> str:
        """Generate the SQL code for the link using AutomateDV."""
        config_str = self._build_config(config_update={"unique_key": self.link_model.src_pk})

        sql =  self._render(
            config_str=config_str,
            source_models=self.source_models,
            src_pk=self.link_model.src_pk,
            src_fk=self.link_model.src_fk,
            src_ldts=self.link_model.src_ldts,
            src_source=self.link_model.src_source,
        )
        self.logger.debug(f"Generated SQL for hub '{self.model.name}':\n{sql}")
        return sql

    @property
    def _template_body(self)-> str:
        return """{{{{
    config(
        {config_str}
    )
}}}}

{{% - set source_model = {source_models} -%}}

{{% - set src_pk       = '{src_pk}' -%}}
{{% - set src_fk       = {src_fk} -%}}
{{% - set src_ldts     = '{src_ldts}' -%}}
{{% - set src_source   = '{src_source}' -%}}

{{{{ automate_dv.link(
    src_pk      = src_pk,
    src_fk      = src_fk,
    src_ldts    = src_ldts,
    src_source  = src_source,
    source_model= source_models
) }}}}"""

