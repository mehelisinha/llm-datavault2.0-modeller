"""
Link component for Data Vault v2.
"""

from typing import List

from .base import DVComponent


class Link(DVComponent):
    """Data Vault Link component."""

    def __init__(
        self,
        name: str,
        source_models: List[str],
        src_pk: str,
        src_fk: List[str],
        src_ldts: str = "LOAD_DATE",
        src_source: str = "RECORD_SOURCE",
        schema: str = "raw_vault",
    ):
        super().__init__(name, schema)
        self.source_models = source_models
        self.src_pk = src_pk
        self.src_fk = src_fk
        self.src_ldts = src_ldts
        self.src_source = src_source

    def generate_sql(self) -> str:
        """Generate the SQL code for the link using AutomateDV."""
        config_params = self.get_config()
        config_params["unique_key"] = self.src_pk

        config_str = ",\n    ".join(
            f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" for k, v in config_params.items()
        )

        sql = """{{
    config(
        {config_str}
    )
}}

{{% set source_models = {source_models} %}}

{{% set src_pk       = '{src_pk}' %}}
{{% set src_fk       = {src_fk} %}}
{{% set src_ldts     = '{src_ldts}' %}}
{{% set src_source   = '{src_source}' %}}

{{{{ automate_dv.link(
    src_pk      = src_pk,
    src_fk      = src_fk,
    src_ldts    = src_ldts,
    src_source  = src_source,
    source_model= source_models
) }}}}""".format(
            config_str=config_str,
            source_models=self.source_models,
            src_pk=self.src_pk,
            src_fk=self.src_fk,
            src_ldts=self.src_ldts,
            src_source=self.src_source,
        )

        return sql
