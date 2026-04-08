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
        equipment_type,
        cast(base_voltage_kv as decimal(10,3)) as base_voltage_kv,
        cast(in_service as boolean)            as in_service,
        asset_status,
        manufacturer,
        model,
        serial_number,
        cast(load_dts as timestamp)            as load_dts,
        record_source,
        cdc_flag,
        current_timestamp()                    as ingested_at

    from {{ source('iec_cim_raw', 'conducting_equipment') }}

    {% if is_incremental() %}
        where cast(load_dts as timestamp) > (select max(load_dts) from {{ this }})
    {% endif %}

)

select * from source