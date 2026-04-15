"""
Satellite component for Data Vault v2.
"""

from logging import Logger
from typing import List

from src.dv_components.components.base import DVBaseRawVaultComponent
from src.dv_components.components.model import DVComponentModel, SatelliteModel


class Satellite(DVBaseRawVaultComponent):
    """Data Vault Satellite component."""

    def __init__(
        self,
        model: DVComponentModel,
        source_models: List[str],
        logger:Logger
    ):
        super().__init__(model=model, source_models=source_models, logger=logger)

        if not isinstance(model.meta, SatelliteModel):
            raise ValueError(f"Expected SatelliteModel, got {type(model.meta)}")
        self.satellite_model: SatelliteModel = model.meta



    def generate(self) -> str:
        """Generate the SQL code for the link using AutomateDV."""
        config_str = self._build_config(config_update={"unique_key": self.satellite_model.src_pk})

        # eff_part = (
        #     "\n{{% set src_eff      = '{src_eff}' %}}".format(src_eff=self.satellite_model.src_eff)
        #     if self.satellite_model.src_eff
        #     else ""
        # )
        # eff_param = ",\n    src_eff     = src_eff" if self.satellite_model.src_eff else ""


        sql =  self._render(
            config_str=config_str,
            source_models=self.source_models,
            src_pk=self.satellite_model.src_pk,
            src_hashdiff=self.satellite_model.src_hashdiff,
            src_payload=self.satellite_model.src_payload,
            src_ldts=self.satellite_model.src_ldts,
            src_source=self.satellite_model.src_source,
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
{{% - set src_hashdiff = '{src_hashdiff}' -%}}
{{% - set src_payload  = {src_payload} -%}}
{{% - set src_ldts     = '{src_ldts}' -%}}
{{% - set src_source   = '{src_source}' -%}}

{{{{ automate_dv.sat(
    source_model= source_models
    src_pk      = src_pk,
    src_hashdiff= src_hashdiff,
    src_payload = src_payload,
    src_ldts    = src_ldts,
    src_source  = src_source,

) }}}}"""
