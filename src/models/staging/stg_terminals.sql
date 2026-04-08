{{
    config(materialized='view', tags=['staging'])
}}

{%- set yaml_metadata -%}
source_model: 'brz_terminals'

derived_columns:
  RECORD_SOURCE:  "record_source"
  LOAD_DATE:      "load_dts"
  EFFECTIVE_FROM: "load_dts"
  CDC_FLAG:       "cdc_flag"

hashed_columns:
  HK_TERMINAL:
    - "mrid"

  HK_CONDUCTING_EQUIPMENT:
    - "conducting_equipment_mrid"

  HK_CONNECTIVITY_NODE:
    - "connectivity_node_mrid"

  HK_TERMINAL_EQUIPMENT_NODE:           # Link hash key
    - "mrid"
    - "conducting_equipment_mrid"
    - "connectivity_node_mrid"

  HASHDIFF_TERMINAL_DETAILS:
    is_hashdiff: true
    columns:
      - "name"
      - "sequence_number"
      - "phases"
      - "connected"

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