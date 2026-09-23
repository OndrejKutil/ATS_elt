-- fct_job_postings
--
-- This model is intended to capture one row per job posting, including its
-- lifecycle and descriptive attributes, for downstream consumption. Not implemented.

{{ config(materialized='view') }}

SELECT
    l.job_id,
    p.title,
    p.company_name,
    p.absolute_url,
    p.employment,
    p.language,
    p.location,
    c.departments,
    c.offices,
    c.content_text,
    l.first_seen,
    l.last_seen,
    l.is_closed,

    current_timestamp() AS dbt_updated_at

FROM {{ ref('int_job_lifecycle') }} AS l
LEFT JOIN {{ ref('stg_job_snapshots') }} AS p ON l.job_id = p.job_id
LEFT JOIN {{ ref('int_job_content') }} AS c ON p.content_hash = c.content_hash