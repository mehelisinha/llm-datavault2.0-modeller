{
    config(
        materialized='incremental',
    incremental_strategy='merge',
    tags=['raw_vault', 'satellite'],
    unique_key='HK_CONNECTIVITY_NODE'
    )
}

{% set source_models = ['stg_connectivity_nodes'] %}

{% set src_pk       = 'HK_CONNECTIVITY_NODE' %}
{% set src_hashdiff = 'HD_CONNECTIVITY_NODE_S' %}
{% set src_payload  = ['name', 'node_type', 'nominal_voltage', 'is_connected'] %}
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