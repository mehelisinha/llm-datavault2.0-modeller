{
    config(
        materialized='incremental',
    incremental_strategy='merge',
    tags=['raw_vault', 'satellite'],
    unique_key='HK_CONDUCTING_EQUIPMENT'
    )
}

{% set source_models = ['stg_conducting_equipment'] %}

{% set src_pk       = 'HK_CONDUCTING_EQUIPMENT' %}
{% set src_hashdiff = 'HD_CONDUCTING_EQUIPMENT_S' %}
{% set src_payload  = ['name', 'equipment_type', 'base_voltage_kv', 'in_service', 'asset_status', 'manufacturer', 'model', 'serial_number'] %}
{% set src_ldts     = 'LOAD_DATE' %}
{% set src_source   = 'RECORD_SOURCE' %}

{{ automate_dv.sat(
    src_pk      = src_pk,
    src_hashdiff= src_hashdiff,
    src_payload = src_payload,
    src_ldts    = src_ldts,
    src_source  = src_source,
    source_model= source_models
) }}