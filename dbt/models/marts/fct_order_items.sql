with items as (
    select * from {{ ref('stg_olist__order_items') }}
),

orders as (
    select * from {{ ref('fct_orders') }}
),

products as (
    select * from {{ ref('dim_products') }}
),

sellers as (
    select * from {{ ref('dim_sellers') }}
)

select
    i.order_item_key,
    i.order_id,
    i.order_item_number,
    i.product_id,
    i.seller_id,
    o.customer_id,
    o.order_status,
    o.purchased_at,
    o.purchase_date,
    o.customer_state,
    s.seller_state,
    pr.product_category,
    i.price,
    i.freight_value,
    i.price + i.freight_value   as item_value
from items i
inner join orders   o  on i.order_id = o.order_id
left join  products pr on i.product_id = pr.product_id
left join  sellers  s  on i.seller_id = s.seller_id
