-- dbt/models/staging/stg_customers.sql
-- Staging model: clean H&M customer data.

{{
  config(
    materialized = 'view',
    description  = 'Clean H&M customer records with loyalty and engagement signals.'
  )
}}

SELECT
    CAST(customer_id              AS STRING) AS customer_id,
    CAST(age                      AS INT64)  AS age,
    CAST(club_member_status       AS STRING) AS club_member_status,
    CAST(fashion_news_frequency   AS STRING) AS fashion_news_frequency,
    CAST(active                   AS BOOL)   AS is_active,

    -- Bucketed age for feature engineering
    CASE
        WHEN CAST(age AS INT64) < 25 THEN 'under_25'
        WHEN CAST(age AS INT64) < 35 THEN '25_34'
        WHEN CAST(age AS INT64) < 50 THEN '35_49'
        ELSE '50_plus'
    END AS age_bucket,

FROM {{ source('shopsignal', 'raw_customers') }}
WHERE customer_id IS NOT NULL
