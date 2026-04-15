{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['HK_TERMINAL_EQUIPMENT_NODE', 'LOAD_DATE'],
        tags=['raw_vault', 'satellite']
    )
}}

-- Effectivity satellite tracks when a Terminal connection is active/inactive.
-- The CDC_FLAG D (Delete) is handled here by setting EFFECTIVE_TO.

{%- set source_models   = 'stg_terminals' -%}
{%- set src_pk          = 'HK_TERMINAL_EQUIPMENT_NODE' -%}
{%- set src_dfk         = 'HK_TERMINAL_EQUIPMENT_NODE' -%}
{%- set src_eff         = 'EFFECTIVE_FROM' -%}
{%- set src_ldts        = 'LOAD_DATE' -%}
{%- set src_source      = 'RECORD_SOURCE' -%}

{{ automate_dv.eff_sat(
    src_pk      = src_pk,
    src_dfk     = src_dfk,
    src_sfk     = none,
    src_start_date = src_eff,
    src_end_date   = none,
    src_eff     = src_eff,
    src_ldts    = src_ldts,
    src_source  = src_source,
    source_model= source_models
) }}