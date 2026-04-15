{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['HK_CONDUCTING_EQUIPMENT', 'LOAD_DATE'],
        tags=['raw_vault', 'satellite']
    )
}}

-- Operational satellite: tracks in_service and asset_status changes.
-- Separate from the details satellite to allow different refresh rates.

{%- set source_models = 'stg_conducting_equipment' -%}
{%- set src_pk        = 'HK_CONDUCTING_EQUIPMENT' -%}
{%- set src_hashdiff  = 'HASHDIFF_CE_OPERATIONAL' -%}
{%- set src_payload   = ['in_service', 'asset_status'] -%}
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
