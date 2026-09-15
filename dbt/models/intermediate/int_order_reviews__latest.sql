-- Some orders have more than one review; keep the most recent.
select
    order_id,
    review_score,
    review_created_at
from {{ ref('stg_olist__order_reviews') }}
qualify row_number() over (
    partition by order_id
    order by review_created_at desc nulls last, review_id
) = 1
