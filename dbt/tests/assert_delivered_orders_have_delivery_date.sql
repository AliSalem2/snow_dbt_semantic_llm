-- Known source issue: a handful of "delivered" orders have no delivery
-- timestamp. Warn instead of fail, so it stays visible without blocking.
{{ config(severity='warn') }}

select order_id
from {{ ref('fct_orders') }}
where order_status = 'delivered'
  and delivered_to_customer_at is null
