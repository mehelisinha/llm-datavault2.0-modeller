"""
Hub component for Data Vault v2.
"""

from logging import Logger

from src.dv_components.models.base import DVBaseStagingComponent
from src.dv_components.models.model import DVComponentModel, StagingModel


class Staging(DVBaseStagingComponent):
    """Data Vault Hub component."""

    def __init__(self, model: DVComponentModel, logger: Logger):
        super().__init__(model=model, logger=logger)

        if not isinstance(model.meta, StagingModel):
            raise ValueError(f"Expected HubMoStagingModeldel, got {type(model.meta)}")
        self.stg_model: StagingModel = model.meta

    def _get_render_kwargs(self) -> dict:
        # When source_name is set, render as a dbt source dict: {'bronze': 'table'}
        # automate_dv.stage() resolves this to {{ source('bronze', 'table') }}
        if self.stg_model.source_name:
            source_ref = {self.stg_model.source_name: self.stg_model.source_model[0]}
            source_model_rendered = repr(source_ref)
        else:
            source_model_rendered = self._formatter.format_list(
                self.stg_model.source_model
            )

        return dict(
            config_options=self._build_config(),
            source_model=source_model_rendered,
            include_source_columns=self.stg_model.include_source_columns,
            hashed_columns=self.stg_model.get_dv_from_field("hashed_columns"),
            derived_columns=self.stg_model.get_dv_from_field("derived_columns"),
            null_columns=self.stg_model.get_dv_from_field("null_columns"),
            ranked_columns=self.stg_model.get_dv_from_field("ranked_columns"),
        )

    @property
    def _template_body(self) -> str:
        return """
<% set rendered = render_config(config_options) %>
<<rendered>>
{%- set source_model   = <<source_model>> -%}
{%- set include_source_columns = <<include_source_columns>> -%}
{%- set derived_columns       = <<derived_columns>> -%}
{%- set null_columns       = <<null_columns>> -%}
{%- set hashed_columns     = <<hashed_columns>> -%}
{%- set ranked_columns   = <<ranked_columns>> -%}

{{ automate_dv.stage(include_source_columns=include_source_columns,
                     source_model=source_model,
                     derived_columns=derived_columns,
                     null_columns=null_columns,
                     hashed_columns=hashed_columns,
                     ranked_columns=ranked_columns) }}
"""


# {% set metadata_dict = fromyaml(yaml_metadata) %}
# {% set source_model = metadata_dict['source_model'] %}
# {% set derived_columns = metadata_dict['derived_columns'] %}
# {% set hashed_columns = metadata_dict['hashed_columns'] %}

if __name__ == "__main__":
    import yaml

    from shared.logger.default_logger import default_logger

    config = """
source_model: ['conducting_equipment']

derived_columns:
  RECORD_SOURCE:  "record_source"
  LOAD_DATE:      "load_dts"
  EFFECTIVE_FROM: "load_dts"
  CDC_FLAG:       "cdc_flag"

hashed_columns:
  HK_CONDUCTING_EQUIPMENT:
    - "mrid"

  HASHDIFF_CE_OPERATIONAL:
    is_hashdiff: true
    columns:
      - "in_service"
      - "asset_status"

  HASHDIFF_CE_DETAILS:
    is_hashdiff: true
    columns:
      - "name"
      - "equipment_type"
      - "base_voltage_kv"
      - "manufacturer"
      - "model"
      - "serial_number"

ranked_columns:
  DBTVAULT_RANK:
    partition_by: "mrid"
    order_by:     "load_dts"
"""

    def parse_staging_config(config_str: str) -> dict:

        raw = yaml.safe_load(config_str)

        # --- derived_columns ---
        derived_columns = []
        # raw_val = raw.get("derived_columns", {}).items()
        # default_logger.debug(f"deriv col: {raw_val}")
        for i, (col, expr) in enumerate(raw.get("derived_columns", {}).items()):
            derived_columns.append(
                {
                    "column_name": col,
                    "expr": expr,
                    "order": i,  # preserve YAML order
                }
            )
        default_logger.debug(f"=============deriv col: {derived_columns}=========")
        # --- hashed_columns ---
        hashed_columns = []
        for col, value in raw.get("hashed_columns", {}).items():
            if isinstance(value, list):
                # simple hash
                hashed_columns.append(
                    {
                        "column_name": col,
                        "is_hashdiff": False,
                        "columns": value,
                    }
                )
            else:
                # hashdiff
                hashed_columns.append(
                    {
                        "column_name": col,
                        "is_hashdiff": value.get("is_hashdiff", False),
                        "columns": value.get("columns", []),
                    }
                )

        # --- ranked_columns ---
        ranked_columns = []
        for col, value in raw.get("ranked_columns", {}).items():
            ranked_columns.append(
                {
                    "column_name": col,
                    "partition_by": value["partition_by"],
                    "order_by": value["order_by"],
                    "dense_rank": value.get("dense_rank", False),
                }
            )

        source_model = (
            [raw["source_model"]]
            if isinstance(raw["source_model"], str)
            else raw["source_model"]
        )
        return {
            "source_model": source_model,
            "derived_columns": derived_columns,
            "hashed_columns": hashed_columns,
            "ranked_columns": ranked_columns,
        }

    stg_model = StagingModel(**parse_staging_config(config))

    model = DVComponentModel(name="conducting_equipment", meta=stg_model)
    #     default_logger.debug(f"""=========== Stg Mode:
    #                          {stg_model.model_dump()}
    # ===========""")
    stg = Staging(model=model, logger=default_logger)
    sql = stg.generate()
