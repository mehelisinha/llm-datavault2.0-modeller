{{
    config(materialized='view', tags=['staging'])
}}

{%- set yaml_metadata -%}
source_model: 'brz_conducting_equipment'

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

{%- endset -%}

{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ automate_dv.stage(
    include_source_columns = true,
    source_model           = metadata_dict['source_model'],
    derived_columns        = metadata_dict['derived_columns'],
    hashed_columns         = metadata_dict['hashed_columns'],
    ranked_columns         = metadata_dict['ranked_columns']
) }}