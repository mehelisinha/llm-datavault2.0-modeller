{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['HK_CONNECTIVITY_NODE', 'LOAD_DATE'],
        tags=['raw_vault', 'satellite']
    )
}}

{%- set source_models = 'stg_connectivity_nodes' -%}
{%- set src_pk        = 'HK_CONNECTIVITY_NODE' -%}
{%- set src_hashdiff  = 'HASHDIFF_CONNECTIVITY_NODE_DETAILS' -%}
{%- set src_payload   = ['name', 'description'] -%}
{%- set src_eff       = 'EFFECTIVE_FROM' -%}
{%- set src_ldts      = 'LOAD_DATE' -%}
{%- set src_source    = 'RECORD_SOURCE' -%}

{{ automate_dv.sat(
    src_pk      = src_pk,
    src_hashdiff= src_hashdiff,
    src_payload = src_payload,
    src_eff     = src_eff,
    src_ldts    = src_ldts,
    src_source  = src_source,
    source_model= source_models
) }}