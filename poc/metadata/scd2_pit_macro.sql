{# macros/scd2_from_sat.sql #}

{% macro scd2_from_sat(
    sat_model,
    pk,
    payload_cols,
    effective_from='EFFECTIVE_FROM',
    ldts='LOAD_DATETIME',
    is_deleted_col=none,
    end_of_time='cast(\'9999-12-31\' as date)'
) %}

with sat as (
    select * from {{ ref(sat_model) }}
),

scd2 as (
    select
        {{ pk }},

        {%- for col in payload_cols %}
        {{ col }},
        {%- endfor %}

        {{ effective_from }}                                      as valid_from,

        coalesce(
            lead({{ effective_from }}) over (
                partition by {{ pk }}
                order by {{ effective_from }}, {{ ldts }}
            ),
            {{ end_of_time }}
        )                                                         as valid_to,

        case
            when lead({{ effective_from }}) over (
                partition by {{ pk }}
                order by {{ effective_from }}, {{ ldts }}
            ) is null
            {%- if is_deleted_col %}
            and {{ is_deleted_col }} = false
            {%- endif %}
            then true
            else false
        end                                                       as is_current

        {%- if is_deleted_col %},
        {{ is_deleted_col }}
        {%- endif %}

    from sat
    {%- if is_deleted_col %}
    -- exclude ghost records
    where {{ pk }} != {{ "'" ~ '0' * 32 ~ "'" }}
    {%- endif %}
)

select * from scd2

{% endmacro %}
