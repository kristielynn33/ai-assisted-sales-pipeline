select
    metric_month,
    region,
    product_category,
    customer_segment,
    count(*) as duplicate_count
from {{ ref('fct_monthly_metrics') }}
group by
    1,
    2,
    3,
    4
having count(*) > 1