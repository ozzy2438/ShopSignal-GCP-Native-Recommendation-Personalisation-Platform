-- dbt/models/marts/fct_user_item_interactions.sql
-- Fact table: user-item interaction matrix for ALS training.
-- Each row is one observed purchase event (implicit feedback, rating=1).

{{
  config(
    materialized = 'table',
    partition_by = {
      'field': 'transaction_date',
      'data_type': 'date',
      'granularity': 'month'
    },
    cluster_by   = ['customer_id'],
    description  = 'User-item interaction fact table for collaborative filtering.'
  )
}}

WITH interactions AS (
    SELECT
        customer_id,
        article_id,
        transaction_date,
        COUNT(*) AS purchase_count,
        SUM(price) AS total_spend

    FROM {{ ref('stg_transactions') }}
    GROUP BY customer_id, article_id, transaction_date
)

SELECT
    customer_id,
    article_id,
    transaction_date,
    purchase_count,
    total_spend,
    -- Implicit confidence weight (higher purchase count → higher confidence)
    1 + LOG(purchase_count) AS implicit_confidence

FROM interactions
