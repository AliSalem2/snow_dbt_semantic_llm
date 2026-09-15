with orders as (
    select * from {{ ref('stg_olist__orders') }}
),

customers as (
    select * from {{ ref('dim_customers') }}
),

items as (
    select * from {{ ref('int_order_items__aggregated') }}
),

payments as (
    select * from {{ ref('int_order_payments__aggregated') }}
),

reviews as (
    select * from {{ ref('int_order_reviews__latest') }}
)

select
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    c.customer_state,
    o.order_status,
    o.purchased_at,
    cast(o.purchased_at as date)                            as purchase_date,
    o.delivered_to_customer_at,
    o.estimated_delivery_date,

    coalesce(i.item_count, 0)                               as item_count,
    coalesce(i.seller_count, 0)                             as seller_count,
    coalesce(i.items_value, 0)                              as items_value,
    coalesce(i.freight_value, 0)                            as freight_value,
    coalesce(i.items_value, 0) + coalesce(i.freight_value, 0) as order_value,
    coalesce(p.payment_value, 0)                            as payment_value,
    p.max_installments,
    r.review_score,

    o.order_status = 'delivered'                            as is_delivered,
    case
        when o.delivered_to_customer_at is not null
        then {{ dbt.datediff('o.purchased_at', 'o.delivered_to_customer_at', 'day') }}
    end                                                     as delivery_days,
    case
        when o.delivered_to_customer_at is null or o.estimated_delivery_date is null then null
        when cast(o.delivered_to_customer_at as date) > o.estimated_delivery_date then true
        else false
    end                                                     as is_delivered_late

from orders o
left join customers c on o.customer_id = c.customer_id
left join items     i on o.order_id = i.order_id
left join payments  p on o.order_id = p.order_id
left join reviews   r on o.order_id = r.order_id
