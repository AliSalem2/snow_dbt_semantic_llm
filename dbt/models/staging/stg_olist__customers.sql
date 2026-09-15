with source as (
    select * from {{ source('olist', 'customers') }}
)

-- customer_id is per order; customer_unique_id identifies the person.
select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix    as zip_code_prefix,
    lower(customer_city)        as city,
    upper(customer_state)       as state
from source
