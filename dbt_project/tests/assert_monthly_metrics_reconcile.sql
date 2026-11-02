with source_totals as (
    select
        cast(date_trunc('month', "date") as date) as metric_month,
        sum(revenue) as expected_revenue,
        sum(units_sold) as expected_units,
        count(*) as expected_records
    from {{ source('raw', 'raw_sales') }}
    group by 1
),

report_totals as (
    select
        metric_month,
        sum(revenue) as actual_revenue,
        sum(units_sold) as actual_units,
        sum(source_record_count) as actual_records
    from {{ ref('fct_monthly_metrics') }}
    group by 1
)

select
    coalesce(s.metric_month, r.metric_month) as metric_month,
    s.expected_revenue,
    r.actual_revenue,
    s.expected_units,
    r.actual_units,
    s.expected_records,
    r.actual_records
from source_totals as s
full outer join report_totals as r
    on s.metric_month = r.metric_month
where
    s.metric_month is null
    or r.metric_month is null
    or r.actual_revenue is null
    or r.actual_units is null
    or r.actual_records is null
    or abs(s.expected_revenue - r.actual_revenue) > 0.000001
    or s.expected_units <> r.actual_units
    or s.expected_records <> r.actual_records