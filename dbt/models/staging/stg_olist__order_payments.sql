with source as (
    select * from {{ source('olist', 'order_payments') }}
)

select
    order_id,
    try_cast(payment_sequential as integer)         as payment_sequence,
    lower(payment_type)                             as payment_type,
    try_cast(payment_installments as integer)       as installments,
    try_cast(payment_value as decimal(12, 2))       as payment_value
from source
