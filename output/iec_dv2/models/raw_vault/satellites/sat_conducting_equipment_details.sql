




{{
    config(

        materialized="incremental",

        incremental_strategy="merge",

        tags=["raw_vault", "satcomponent"],

        unique_key=["HK_CONDUCTING_EQUIPMENT", "LOAD_DATE"]

    )
}}

{%- set source_model = 'stg_conducting_equipment' -%}
{%- set src_pk       = 'HK_CONDUCTING_EQUIPMENT' -%}
{%- set src_hashdiff = 'HASHDIFF_CE_DETAILS' -%}
{%- set src_payload  = ['name', 'equipment_type', 'base_voltage_kv', 'manufacturer', 'model', 'serial_number'] -%}
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