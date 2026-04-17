




{{
    config(

        materialized="incremental",

        incremental_strategy="merge",

        tags=["raw_vault", "satellite"],

        unique_key=["HK_TERMINAL", "LOAD_DATE"]

    )
}}

{%- set source_model = ['stg_terminals'] -%}
{%- set src_pk       = 'HK_TERMINAL' -%}
{%- set src_hashdiff = 'HASHDIFF_TERMINAL_DETAILS' -%}
{%- set src_payload  = ['name', 'sequence_number', 'phases', 'connected'] -%}
{%- set src_ldts     = 'LOAD_DATE' -%}
{%- set src_source   = 'IEC61968_CIM_v2.0' -%}
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