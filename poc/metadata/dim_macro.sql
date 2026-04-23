-- models/marts/dim_customer.sql
{{ config(materialized='table') }}

{%- set yaml_metadata -%}
sat_model: sat_customer_detail
pk: CUSTOMER_HK
payload_cols:
  - NAME
  - ADDRESS
  - PHONE
is_deleted_col: IS_DELETED
effective_from: EFFECTIVE_FROM
ldts: LOAD_DATETIME
{%- endset -%}

{% set metadata_dict = fromyaml(yaml_metadata) %}

{{ scd2_from_sat(
    sat_model      = metadata_dict['sat_model'],
    pk             = metadata_dict['pk'],
    payload_cols   = metadata_dict['payload_cols'],
    effective_from = metadata_dict['effective_from'],
    ldts           = metadata_dict['ldts'],
    is_deleted_col = metadata_dict['is_deleted_col']
) }}
