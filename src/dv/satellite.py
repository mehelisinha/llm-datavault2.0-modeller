"""
Satellite component for Data Vault v2.
"""

from typing import List, Optional

from .base import DVComponent


class Satellite(DVComponent):
    """Data Vault Satellite component."""

    def __init__(
        self,
        name: str,
        source_models: List[str],
        src_pk: str,
        src_hashdiff: str,
        src_payload: List[str],
        src_ldts: str = "LOAD_DATE",
        src_source: str = "RECORD_SOURCE",
        src_eff: Optional[str] = None,
        schema: str = "raw_vault",
    ):
        super().__init__(name, schema)
        self.source_models = source_models
        self.src_pk = src_pk
        self.src_hashdiff = src_hashdiff
        self.src_payload = src_payload
        self.src_ldts = src_ldts
        self.src_source = src_source
        self.src_eff = src_eff

    def generate_sql(self) -> str:
        """Generate the SQL code for the satellite using AutomateDV."""
        config_params = self.get_config()
        config_params["unique_key"] = self.src_pk

        config_str = ",\n    ".join(
            f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" for k, v in config_params.items()
        )

        eff_part = (
            "\n{{% set src_eff      = '{src_eff}' %}}".format(src_eff=self.src_eff)
            if self.src_eff
            else ""
        )
        eff_param = ",\n    src_eff     = src_eff" if self.src_eff else ""

        sql = """{{
    config(
        {config_str}
    )
}}

{{% set source_models = {source_models} %}}

{{% set src_pk       = '{src_pk}' %}}
{{% set src_hashdiff = '{src_hashdiff}' %}}
{{% set src_payload  = {src_payload} %}}
{{% set src_ldts     = '{src_ldts}' %}}
{{% set src_source   = '{src_source}' %}}{eff_part}

{{{{ automate_dv.sat(
    src_pk      = src_pk,
    src_hashdiff= src_hashdiff,
    src_payload = src_payload,
    src_ldts    = src_ldts,
    src_source  = src_source{eff_param},
    source_model= source_models
) }}}}""".format(
            config_str=config_str,
            source_models=self.source_models,
            src_pk=self.src_pk,
            src_hashdiff=self.src_hashdiff,
            src_payload=self.src_payload,
            src_ldts=self.src_ldts,
            src_source=self.src_source,
            eff_part=eff_part,
            eff_param=eff_param,
        )

        return sql
