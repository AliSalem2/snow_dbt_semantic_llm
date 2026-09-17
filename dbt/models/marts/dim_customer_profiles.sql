-- One row per customer (customer_unique_id).
-- Only orders that were not canceled or unavailable count as purchases.
with orders as (
    select
        order_id,
        customer_unique_id,
        customer_state,
        purchased_at,
        purchase_date
    from {{ ref('fct_orders') }}
    where order_status not in ('canceled', 'unavailable')
),

ranked as (
    select
        *,
        row_number() over (
            partition by customer_unique_id
            order by purchased_at, order_id
        ) as order_seq,
        row_number() over (
            partition by customer_unique_id
            order by purchased_at desc, order_id desc
        ) as order_seq_desc
    from orders
),

customer_orders as (
    select
        customer_unique_id,
        count(*)                                                  as order_count,
        min(purchase_date)                                        as first_purchase_date,
        max(purchase_date)                                        as last_purchase_date,
        max(case when order_seq = 2 then purchase_date end)       as second_purchase_date,
        max(case when order_seq_desc = 1 then customer_state end) as home_state
    from ranked
    group by customer_unique_id
),

data_window as (
    select max(purchase_date) as data_end_date
    from orders
)

select
    c.customer_unique_id,
    c.first_purchase_date,
    c.last_purchase_date,
    c.home_state,
    c.order_count,
    c.order_count > 1 as is_repeat_customer,
    -- Null when the first order is less than 90 days before the end of
    -- the data, so the customer had no full window to come back.
    case
        when {{ dbt.dateadd('day', 90, 'c.first_purchase_date') }} > w.data_end_date then null
        when c.second_purchase_date is not null
         and {{ dbt.datediff('c.first_purchase_date', 'c.second_purchase_date', 'day') }} <= 90 then true
        else false
    end as repeated_within_90d
from customer_orders c
cross join data_window w