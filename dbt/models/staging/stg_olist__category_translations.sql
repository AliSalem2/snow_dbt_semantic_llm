with source as (
    select * from {{ source('olist', 'product_category_translation') }}
)

select
    product_category_name           as category_name_pt,
    product_category_name_english   as category_name_en
from source
