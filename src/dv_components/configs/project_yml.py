

from logging import Logger

import yaml

from src.dv_components.components.base import DVBaseComponent
from src.dv_components.components.model import DVProjectModel


class DBTProject(DVBaseComponent):
    """Class to generate a dbt_project.yml configuration."""
    FORMAT:str = 'yml'

    def __init__(
        self,
        name: str,
        model:DVProjectModel,
        logger:Logger
    ):

        super().__init__(model=model, source_models=[], logger=logger)

        if not isinstance(model.dv_type, DVProjectModel):
            raise ValueError(f"Expected Project Model, got {type(model.dv_type)}")
        self.name = name
        self.model = model
        self.logger=logger
        # self.vars = vars or {
        #     "load_date": "{{ run_started_at.strftime('%Y-%m-%d') }}",
        #     "record_source": "IEC61968_CIM",
        # }

    def get_config(self):

        # prefix_sat =  f"{DvModelNames.SATELLITE.value}_"
        # prefix_eff_sat =  f"{DvModelNames.EFF_SATELLITE.value}_"
        # prefx_hub =  f"{DvModelNames.HUB.value}_"
        # prefix_link = f"{DvModelNames.LINK.value}_"

        models = {
            self.name: {}
        }

        if self.model.stg_schema:
            models[self.name]["staging"] = {
                    "+schema": self.model.stg_schema,
                    "+materialized": "view",
                    "+tags": ["staging"],
                }

        if self.model.raw_vault_schema:
            models[self.name]["raw_vault"] = {
                    "+schema": self.model.raw_vault_schema,
                    "+tags": ["raw_vault"],
                    "hubs": {
                        "+materialized": "incremental",
                        "+incremental_strategy": "merge",
                        # "+unique_key": "hk_{{ this.name | replace('{prefix_hub}', '') }}",
                    },
                    "links": {
                        "+materialized": "incremental",
                        "+incremental_strategy": "merge",
                        # "+unique_key": "hk_{{ this.name | replace('{prefix_link}', '') }}",
                    },
                    "satellites": {
                        "+materialized": "incremental",
                        "+incremental_strategy": "merge",
                        # "+unique_key": ["hk_{{ this.name | replace('{prefix_sat}', '' | replace('{prefix_eff_sat}', '') }}", "load_dts"],
                    },
                }

        if self.model.business_vault_schema:
            models[self.name]["business_vault"] = {
                    "+schema": self.model.business_vault_schema,
                    "+materialized": "table",
                    "+tags": ["business_vault"],
                }
        return models

    def generate(self) -> str:
        """Return the dbt_project.yml content as a YAML string."""
        project_dict = {
            **self.model.model_dump(),
            "models": self.get_config(),
        }

        # Dump YAML with proper formatting
        self.logger.debug(f"Generated dbt_project.yml content:\n{yaml.dump(project_dict, sort_keys=False, default_flow_style=False)}")
        return yaml.dump(project_dict, sort_keys=False, default_flow_style=False)


# Example usage:
# dbt_project = DBTProject(name="iec_dv2")
# yaml_content = dbt_project.generate_yaml()
# print(yaml_content)
