




{{
    config(

        materialized="view",

        tags=["staging"]

    )
}}

{%- set source_model   = {'bronze': 'brz_connectivity_nodes'} -%}
{%- set include_source_columns = True -%}
{%- set derived_columns       = {'RECORD_SOURCE': 'record_source', 'LOAD_DATE': 'load_dts', 'EFFECTIVE_FROM': 'load_dts', 'CDC_FLAG': 'cdc_flag'} -%}
{%- set null_columns       = None -%}
{%- set hashed_columns     = {'HK_CONNECTIVITY_NODE': {'is_hashdiff': False, 'columns': ['mrid']}, 'HASHDIFF_CONNECTIVITY_NODE_DETAILS': {'is_hashdiff': True, 'columns': ['name', 'description']}} -%}
{%- set ranked_columns   = {'DBTVAULT_RANK': {'partition_by': 'mrid', 'order_by': 'load_dts', 'dense_rank': False}} -%}

{{ automate_dv.stage(include_source_columns=include_source_columns,
                     source_model=source_model,
                     derived_columns=derived_columns,
                     null_columns=null_columns,
                     hashed_columns=hashed_columns,
                     ranked_columns=ranked_columns) }}