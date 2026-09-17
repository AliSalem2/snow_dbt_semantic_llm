# Evaluation results

20 business questions, graded against hand-written SQL.

| Mode | Correct | Accuracy | Avg tool calls | Avg seconds |
|---|---|---|---|---|
| Semantic layer | 20/20 | 100% | 1.9 | 6.3 |
| Raw text-to-SQL | 17/20 | 85% | 0.9 | 4.2 |

## Per question

| # | Question | semantic | sql |
|---|---|---|---|
| q01 | What was the total revenue in 2017? | pass | pass |
| q02 | How many orders were placed in 2018? | pass | pass |
| q03 | Which state brings the highest revenue, and how much? | pass | pass |
| q04 | What is the average order value overall? | pass | pass |
| q05 | What share of deliveries arrived later than estimated in 2018? | pass | pass |
| q06 | How many days does delivery take on average? | pass | pass |
| q07 | What is the average review score? | pass | pass |
| q08 | Which product category earns the most, and how much? | pass | fail |
| q09 | How many items were sold in total? | pass | pass |
| q10 | How many customers placed at least one valid order, excluding canceled and unavailable ones? | pass | pass |
| q11 | What share of customers order more than once? | pass | pass |
| q12 | What share of customers come back within 90 days of their first order? | pass | fail |
| q13 | Where do most new customers come from? Give the top three states. | pass | pass |
| q14 | Which month had the highest revenue? | pass | pass |
| q15 | How did revenue in the first quarter of 2018 compare with the fourth quarter of 2017? | pass | pass |
| q16 | Do repeat customers spend more per order than one-time customers? | pass | pass |
| q17 | Which seller state generates the most product revenue? | pass | fail |
| q18 | Which product is the most profitable? | pass | pass |
| q19 | What is the gross margin by product category? | pass | pass |
| q20 | How many customers churned last month? | pass | pass |

## Failures

- **q08 (sql)**: Revenue figure for health_beauty is significantly off (1.44M vs 1.26M).
- **q12 (sql)**: Answer states 1.89% repeat rate vs correct 2.31%, outside tolerance
- **q17 (sql)**: grader returned: 
