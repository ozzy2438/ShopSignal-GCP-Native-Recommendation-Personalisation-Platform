-- dbt/models/marts/fct_user_features.sql
-- User-level feature mart consumed by the LightGBM ranker.

{{
  config(
    materialized = 'table',
    cluster_by   = ['customer_id'],
    description  = 'User-level features for the LightGBM ranking model.'
  )
}}

WITH tx_stats AS (
    SELECT
        customer_id,
        COUNT(DISTINCT article_id)    AS total_unique_items,
        COUNT(*)                      AS total_purchases,
        SUM(price)                    AS total_spend,
        AVG(price)                    AS avg_item_price,
        COUNT(DISTINCT transaction_date) AS active_days,
        MAX(transaction_date)         AS last_purchase_date,
        MIN(transaction_date)         AS first_purchase_date
    FROM {{ ref('stg_transactions') }}
    GROUP BY customer_id
)

SELECT
    t.customer_id,
    c.age,
    c.age_bucket,
    c.club_member_status,
    c.fashion_news_frequency,
    c.is_active,
    t.total_unique_items,
    t.total_purchases,
    t.total_spend,
    t.avg_item_price,
    t.active_days,
    t.last_purchase_date,
    t.first_purchase_date,
    DATE_DIFF(CURRENT_DATE(), t.last_purchase_date, DAY) AS days_since_last_purchase
FROM tx_stats t
LEFT JOIN {{ ref('stg_customers') }} c USING (customer_id)
