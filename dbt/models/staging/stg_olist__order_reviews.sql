-- review_id is not unique in the source (814 duplicates found in phase 1):
-- the same review can be attached to several orders. The grain here is
-- review_id + order_id, deduplicated defensively.
with source as (
    select * from {{ source('olist', 'order_reviews') }}
),

typed as (
    select
        review_id,
        order_id,
        try_cast(review_score as integer)               as review_score,
        review_comment_title                            as comment_title,
        review_comment_message                          as comment_message,
        try_cast(review_creation_date as timestamp)     as review_created_at,
        try_cast(review_answer_timestamp as timestamp)  as review_answered_at
    from source
)

select *
from typed
qualify row_number() over (
    partition by review_id, order_id
    order by review_answered_at desc nulls last
) = 1
