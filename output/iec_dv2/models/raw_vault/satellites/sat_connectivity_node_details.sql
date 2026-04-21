




{{
    config(

        materialized="incremental",

        incremental_strategy="merge",

        tags=["raw_vault", "satellite"],

        unique_key=["HK_CONNECTIVITY_NODE", "LOAD_DATE"]

    )
}}

{%- set source_model = 'stg_connectivity_nodes' -%}
{%- set src_pk       = 'HK_CONNECTIVITY_NODE' -%}
{%- set src_hashdiff = 'HASHDIFF_CONNECTIVITY_NODE_DETAILS' -%}
{%- set src_payload  = ['name', 'description'] -%}
{%- set src_ldts     = 'LOAD_DATE' -%}
{%- set src_source   = 'RECORD_SOURCE' -%}
{%- set src_eff      = 'EFFECTIVE_FROM' -%}
{{ automate_dv.sat(
    src_pk      = src_pk,
    src_hashdiff= src_hashdiff,
    src_payload = src_payload,
    src_ldts    = src_ldts,
    src_source  = src_source,
    src_eff     = src_eff,
    source_model= source_model
) }}