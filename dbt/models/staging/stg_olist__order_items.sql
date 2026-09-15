with source as (
    select * from {{ source('olist', 'order_items') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['order_id', 'order_item_id']) }} as order_item_key,
    order_id,
    try_cast(order_item_id as integer)              as order_item_number,
    product_id,
    seller_id,
    try_cast(shipping_limit_date as timestamp)      as shipping_limit_at,
    try_cast(price as decimal(12, 2))               as price,
    try_cast(freight_value as decimal(12, 2))       as freight_value
from source
