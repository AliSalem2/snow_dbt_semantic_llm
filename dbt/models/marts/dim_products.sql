with products as (
    select * from {{ ref('stg_olist__products') }}
),

translations as (
    select * from {{ ref('stg_olist__category_translations') }}
)

select
    p.product_id,
    -- Some categories have no English translation; fall back to Portuguese.
    coalesce(t.category_name_en, p.category_name_pt, 'unknown') as product_category,
    p.weight_g,
    p.length_cm,
    p.height_cm,
    p.width_cm,
    p.photos_qty
from products p
left join translations t
    on p.category_name_pt = t.category_name_pt
