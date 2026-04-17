




{{
    config(

        materialized="incremental",

        incremental_strategy="merge",

        tags=["raw_vault", "hub"],

        unique_key="HK_TERMINAL"

    )
}}

{%- set source_model = ['stg_terminals'] -%}
{%- set src_pk       = 'HK_TERMINAL' -%}
{%- set src_nk       = 'mrid' -%}
{%- set src_ldts     = 'LOAD_DATE' -%}
{%- set src_source   = 'IEC61968_CIM_v2.0' -%}
{{ automate_dv.hub(
    src_pk      = src_pk,
    src_nk      = src_nk,
    src_ldts    = src_ldts,
    src_source  = src_source,
    source_model= source_model
) }}