




{{
    config(

        materialized="view",

        tags=["staging"]

    )
}}

{%- set source_model   = {'bronze': 'conducting_equipment'} -%}
{%- set include_source_columns = True -%}
{%- set derived_columns       = {'RECORD_SOURCE': 'record_source', 'LOAD_DATE': 'load_dts', 'EFFECTIVE_FROM': 'load_dts', 'CDC_FLAG': 'cdc_flag'} -%}
{%- set null_columns       = None -%}
{%- set hashed_columns     = {'HK_CONDUCTING_EQUIPMENT': {'is_hashdiff': False, 'columns': ['mrid']}, 'HASHDIFF_CE_OPERATIONAL': {'is_hashdiff': True, 'columns': ['in_service', 'asset_status']}, 'HASHDIFF_CE_DETAILS': {'is_hashdiff': True, 'columns': ['name', 'equipment_type', 'base_voltage_kv', 'manufacturer', 'model', 'serial_number']}} -%}
{%- set ranked_columns   = {'DBTVAULT_RANK': {'partition_by': 'mrid', 'order_by': 'load_dts', 'dense_rank': False}} -%}

{{ automate_dv.stage(include_source_columns=include_source_columns,
                     source_model=source_model,
                     derived_columns=derived_columns,
                     null_columns=null_columns,
                     hashed_columns=hashed_columns,
                     ranked_columns=ranked_columns) }}