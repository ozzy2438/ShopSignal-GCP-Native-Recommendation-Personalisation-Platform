-- dbt/models/staging/stg_articles.sql
-- Staging model: clean H&M article (product) catalogue.

{{
  config(
    materialized = 'view',
    description  = 'Clean H&M product catalogue with typed and renamed columns.'
  )
}}

SELECT
    CAST(article_id          AS STRING) AS article_id,
    CAST(product_type_name   AS STRING) AS product_type_name,
    CAST(product_group_name  AS STRING) AS product_group_name,
    CAST(graphical_appearance_name AS STRING) AS graphical_appearance_name,
    CAST(colour_group_name   AS STRING) AS colour_group_name,
    CAST(department_name     AS STRING) AS department_name,
    CAST(index_group_name    AS STRING) AS index_group_name,
    CAST(section_name        AS STRING) AS section_name,
    CAST(garment_group_name  AS STRING) AS garment_group_name,
    CAST(detail_desc         AS STRING) AS detail_desc  -- used for semantic search

FROM {{ source('shopsignal', 'raw_articles') }}
WHERE article_id IS NOT NULL
