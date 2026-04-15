{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='HK_TERMINAL',
        tags=['raw_vault', 'hub']
    )
}}

{%- set source_models = ['stg_terminals'] -%}

{%- set src_pk       = 'HK_TERMINAL' -%}
{%- set src_nk       = 'mrid' -%}
{%- set src_ldts     = 'LOAD_DATE' -%}
{%- set src_source   = 'RECORD_SOURCE' -%}

{{ automate_dv.hub(
    src_pk      = src_pk,
    src_nk      = src_nk,
    src_ldts    = src_ldts,
    src_source  = src_source,
    source_model= source_models
) }}
