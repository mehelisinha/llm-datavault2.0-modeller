




{{
    config(

        materialized="incremental",

        incremental_strategy="merge",

        tags=["raw_vault", "effsatcomponent"],

        unique_key=["HK_TERMINAL_EQUIPMENT_NODE", "LOAD_DATE"]

    )
}}

{%- set source_model = 'stg_terminals' -%}
{%- set src_pk       = 'HK_TERMINAL_EQUIPMENT_NODE' -%}
{%- set src_dfk      = 'HK_TERMINAL' -%}
{%- set src_sfk      = ['HK_CONDUCTING_EQUIPMENT', 'HK_CONNECTIVITY_NODE'] -%}

{%- set src_start_date = 'START_DATE' -%}

{%- set src_eff      = 'EFFECTIVE_FROM' -%}
{%- set src_ldts     = 'LOAD_DATE' -%}
{%- set src_source   = 'RECORD_SOURCE' -%}
{{ automate_dv.eff_sat(
    src_pk         = src_pk,
    src_dfk        = src_dfk,
    src_sfk        = src_sfk,
    src_start_date = src_start_date,
    src_eff        = src_eff,
    src_ldts       = src_ldts,
    src_source     = src_source,
    source_model   = source_model
) }}
