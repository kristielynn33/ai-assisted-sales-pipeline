select
    cast(date_trunc('month', sale_date) as date) as metric_month,
    region,
    product_category,
    customer_segment,
    sum(revenue) as revenue,
    sum(units_sold) as units_sold,
    count(*) as source_record_count
from {{ ref('stg_sales') }}
group by
    1,
    2,
    3,
    4