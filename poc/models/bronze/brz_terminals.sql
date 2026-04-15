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
        conducting_equipment_mrid,
        connectivity_node_mrid,
        cast(sequence_number as int)    as sequence_number,
        phases,
        cast(connected as boolean)      as connected,
        cast(load_dts as timestamp)     as load_dts,
        record_source,
        cdc_flag,
        current_timestamp()             as ingested_at

    from {{ source('iec_cim_raw', 'terminals') }}

    {% if is_incremental() %}
        where cast(load_dts as timestamp) > (select max(load_dts) from {{ this }})
    {% endif %}

)

select * from source
