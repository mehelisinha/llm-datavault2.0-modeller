




{{
    config(

        materialized="incremental",

        incremental_strategy="merge",

        tags=["raw_vault", "hub"],

        unique_key="HK_CONDUCTING_EQUIPMENT"

    )
}}

{%- set source_model = ['stg_conducting_equipment'] -%}
{%- set src_pk       = 'HK_CONDUCTING_EQUIPMENT' -%}
{%- set src_nk       = 'mrid' -%}
{%- set src_ldts     = 'LOAD_DATE' -%}
{%- set src_source   = 'RECORD_SOURCE' -%}
{{ automate_dv.hub(
    src_pk      = src_pk,
    src_nk      = src_nk,
    src_ldts    = src_ldts,
    src_source  = src_source,
    source_model= source_model
) }}