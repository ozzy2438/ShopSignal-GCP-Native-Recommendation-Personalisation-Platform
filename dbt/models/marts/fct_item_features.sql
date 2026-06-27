-- dbt/models/marts/fct_item_features.sql
-- Item-level feature mart consumed by the LightGBM ranker.

{{
  config(
    materialized = 'table',
    cluster_by   = ['article_id'],
    description  = 'Item-level features for the LightGBM ranking model.'
  )
}}

WITH item_stats AS (
    SELECT
        article_id,
        COUNT(DISTINCT customer_id) AS unique_buyers,
        COUNT(*)                    AS total_purchases,
        SUM(price)                  AS total_revenue,
        AVG(price)                  AS avg_price,
        MAX(transaction_date)       AS last_sold_date
    FROM {{ ref('stg_transactions') }}
    GROUP BY article_id
)

SELECT
    a.article_id,
    a.product_type_name,
    a.product_group_name,
    a.colour_group_name,
    a.department_name,
    a.index_group_name,
    a.section_name,
    a.garment_group_name,
    -- Popularity features
    COALESCE(s.unique_buyers,   0) AS unique_buyers,
    COALESCE(s.total_purchases, 0) AS total_purchases,
    COALESCE(s.avg_price,       0) AS avg_price,
    s.last_sold_date,
    DATE_DIFF(CURRENT_DATE(), s.last_sold_date, DAY) AS days_since_last_sold,
    -- Normalised popularity score (0–1)
    SAFE_DIVIDE(
        COALESCE(s.unique_buyers, 0),
        MAX(COALESCE(s.unique_buyers, 0)) OVER ()
    ) AS popularity_score
FROM {{ ref('stg_articles') }} a
LEFT JOIN item_stats s USING (article_id)
