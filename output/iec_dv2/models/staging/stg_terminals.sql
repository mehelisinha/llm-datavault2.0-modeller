




{{
    config(

        materialized="view",

        tags=["staging", "stagingcomponent"]

    )
}}

{%- set source_model   = {'bronze': 'terminals'} -%}
{%- set include_source_columns = True -%}
{%- set derived_columns       = {'RECORD_SOURCE': 'record_source', 'LOAD_DATE': 'load_dts', 'EFFECTIVE_FROM': 'load_dts', 'START_DATE': 'load_dts', 'END_DATE': "CASE WHEN OPERATION_TYPE = 'D' THEN CURRENT_TIMESTAMP ELSE CAST('9999-12-31' AS DATE) END", 'IS_DELETED': "CASE WHEN OPERATION_TYPE = 'D' THEN TRUE ELSE FALSE END"} -%}
{%- set null_columns       = None -%}
{%- set hashed_columns     = {'HK_TERMINAL': ['mrid'], 'HK_CONDUCTING_EQUIPMENT': ['conducting_equipment_mrid'], 'HK_CONNECTIVITY_NODE': ['connectivity_node_mrid'], 'HK_TERMINAL_EQUIPMENT_NODE': ['mrid', 'conducting_equipment_mrid', 'connectivity_node_mrid'], 'HASHDIFF_TERMINAL_DETAILS': {'is_hashdiff': True, 'columns': ['name', 'sequence_number', 'phases', 'connected']}} -%}
{%- set ranked_columns   = {'DBTVAULT_RANK': {'partition_by': 'mrid', 'order_by': 'load_dts', 'dense_rank': False}} -%}

{{ automate_dv.stage(include_source_columns=include_source_columns,
                     source_model=source_model,
                     derived_columns=derived_columns,
                     null_columns=null_columns,
                     hashed_columns=hashed_columns,
                     ranked_columns=ranked_columns) }}