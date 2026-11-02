select
    "date" as sale_date,
    region,
    product_category,
    revenue,
    units_sold,
    customer_segment
from {{ source('raw', 'raw_sales') }}