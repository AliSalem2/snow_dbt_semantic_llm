select
    order_id,
    count(*)            as payment_count,
    sum(payment_value)  as payment_value,
    max(installments)   as max_installments
from {{ ref('stg_olist__order_payments') }}
group by order_id
