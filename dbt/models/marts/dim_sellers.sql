select
    seller_id,
    zip_code_prefix,
    city    as seller_city,
    state   as seller_state
from {{ ref('stg_olist__sellers') }}
