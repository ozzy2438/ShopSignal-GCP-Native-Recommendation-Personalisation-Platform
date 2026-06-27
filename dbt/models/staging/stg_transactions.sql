-- dbt/models/staging/stg_transactions.sql
-- Staging model: clean and type-cast raw H&M transaction data.
-- Source: shopsignal.raw_transactions (loaded by src/data/upload_to_bq.py)
--
-- TODO(feat/data-pipeline): materialise after raw tables are loaded to BigQuery.

{{
  config(
    materialized = 'view',
    description  = 'Cleaned H&M transaction events with typed columns.'
  )
}}

SELECT
    CAST(t_dat          AS DATE)    AS transaction_date,
    CAST(customer_id    AS STRING)  AS customer_id,
    CAST(article_id     AS STRING)  AS article_id,
    CAST(price          AS FLOAT64) AS price,
    CAST(sales_channel_id AS INT64) AS sales_channel_id,

    -- Derived columns
    EXTRACT(YEAR  FROM CAST(t_dat AS DATE)) AS transaction_year,
    EXTRACT(MONTH FROM CAST(t_dat AS DATE)) AS transaction_month,
    EXTRACT(WEEK  FROM CAST(t_dat AS DATE)) AS transaction_week,

FROM {{ source('shopsignal', 'raw_transactions') }}
WHERE customer_id IS NOT NULL
  AND article_id  IS NOT NULL
  AND price       > 0
