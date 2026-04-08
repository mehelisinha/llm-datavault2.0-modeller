{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='HK_TERMINAL_EQUIPMENT_NODE',
        tags=['raw_vault', 'link']
    )
}}

-- This link records the relationship:
-- Terminal  ──  ConductingEquipment  ──  ConnectivityNode
-- Captures the network topology graph edge

{%- set source_models = 'stg_terminals' -%}

{%- set src_pk  = 'HK_TERMINAL_EQUIPMENT_NODE' -%}

{%- set src_fk  = [
    'HK_TERMINAL',
    'HK_CONDUCTING_EQUIPMENT',
    'HK_CONNECTIVITY_NODE'
] -%}

{%- set src_ldts   = 'LOAD_DATE' -%}
{%- set src_source = 'RECORD_SOURCE' -%}

{{ automate_dv.link(
    src_pk      = src_pk,
    src_fk      = src_fk,
    src_ldts    = src_ldts,
    src_source  = src_source,
    source_model= source_models
) }}