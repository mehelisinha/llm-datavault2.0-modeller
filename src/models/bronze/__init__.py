{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        partition_by={'field': 'load_dts', 'data_type': 'date'},
        tags=['bronze']
    )
}}

with source as (

    select
        mrid,
        name,
        description,
        cast(load_dts as timestamp)   as load_dts,
        record_source,
        cdc_flag,
        current_timestamp()           as ingested_at

    from {{ source('iec_cim_raw', 'connectivity_nodes') }}

    {% if is_incremental() %}
        where cast(load_dts as timestamp) > (select max(load_dts) from {{ this }})
    {% endif %}

)

select * from source