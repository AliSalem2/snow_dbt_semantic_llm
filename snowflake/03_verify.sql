-- =====================================================================
-- 03_verify.sql
-- Row counts against the published Kaggle figures, plus checks whose
-- results feed the dbt tests in phase 2.
-- =====================================================================
USE ROLE LOADER;
USE WAREHOUSE LOADING_WH;
USE SCHEMA RAW.OLIST;

-- 1. Row counts (every status should be OK)
WITH counts AS (
            SELECT 'CUSTOMERS' AS tbl,            COUNT(*) AS actual,   99441 AS expected FROM CUSTOMERS
  UNION ALL SELECT 'GEOLOCATION',                 COUNT(*),           1000163             FROM GEOLOCATION
  UNION ALL SELECT 'ORDERS',                      COUNT(*),             99441             FROM ORDERS
  UNION ALL SELECT 'ORDER_ITEMS',                 COUNT(*),            112650             FROM ORDER_ITEMS
  UNION ALL SELECT 'ORDER_PAYMENTS',              COUNT(*),            103886             FROM ORDER_PAYMENTS
  UNION ALL SELECT 'ORDER_REVIEWS',               COUNT(*),             99224             FROM ORDER_REVIEWS
  UNION ALL SELECT 'PRODUCTS',                    COUNT(*),             32951             FROM PRODUCTS
  UNION ALL SELECT 'SELLERS',                     COUNT(*),              3095             FROM SELLERS
  UNION ALL SELECT 'PRODUCT_CATEGORY_TRANSLATION',COUNT(*),                71             FROM PRODUCT_CATEGORY_TRANSLATION
)
SELECT tbl, actual, expected,
       IFF(actual = expected, 'OK', 'CHECK') AS status
FROM counts
ORDER BY tbl;

-- 2. Primary key candidates (note any non-zero result for phase 2 tests)
SELECT 'orders.order_id' AS key_check, COUNT(*) - COUNT(DISTINCT ORDER_ID) AS duplicates FROM ORDERS
UNION ALL SELECT 'customers.customer_id',   COUNT(*) - COUNT(DISTINCT CUSTOMER_ID) FROM CUSTOMERS
UNION ALL SELECT 'products.product_id',     COUNT(*) - COUNT(DISTINCT PRODUCT_ID)  FROM PRODUCTS
UNION ALL SELECT 'sellers.seller_id',       COUNT(*) - COUNT(DISTINCT SELLER_ID)   FROM SELLERS
UNION ALL SELECT 'order_reviews.review_id', COUNT(*) - COUNT(DISTINCT REVIEW_ID)   FROM ORDER_REVIEWS;

-- 3. Date range (sanity for time-based metrics later)
SELECT MIN(TRY_TO_TIMESTAMP(ORDER_PURCHASE_TIMESTAMP)) AS first_order,
       MAX(TRY_TO_TIMESTAMP(ORDER_PURCHASE_TIMESTAMP)) AS last_order,
       COUNT_IF(TRY_TO_TIMESTAMP(ORDER_PURCHASE_TIMESTAMP) IS NULL) AS unparseable_timestamps
FROM ORDERS;

-- 4. Order status mix
SELECT ORDER_STATUS, COUNT(*) AS orders
FROM ORDERS
GROUP BY 1
ORDER BY 2 DESC;

-- 5. Review scores should only be 1 to 5 (anything else means broken
--    multi-line parsing)
SELECT REVIEW_SCORE, COUNT(*) AS n
FROM ORDER_REVIEWS
GROUP BY 1
ORDER BY 1;
