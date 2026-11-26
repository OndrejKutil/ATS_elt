{{ config(materialized='table') }}

WITH attributes_at_last_seen AS (

    SELECT
        job_id,
        company_slug,
        company_name,
        absolute_url,
        employment,
        language,
        title,
        location,
        content_hash,
        first_published
    FROM {{ ref('stg_job_snapshots') }}
    QUALIFY row_number() OVER (
        PARTITION BY job_id, company_slug
        ORDER BY dt DESC
    ) = 1

)

SELECT
    l.job_id,
    l.company_slug,
    p.company_name,
    p.title,
    p.absolute_url,
    p.employment,
    p.language,
    p.location,
    p.first_published,
    c.departments,
    c.offices,
    c.content_text,
    c.content_word_count,
    l.first_seen,
    l.last_seen,
    l.is_closed,
    date_diff('day', l.first_seen, l.last_seen) + 1 AS days_observed,

    {{ dbt.current_timestamp() }} AS dbt_updated_at

FROM {{ ref('int_job_lifecycle') }} AS l
INNER JOIN attributes_at_last_seen AS p
    ON  l.job_id       = p.job_id
    AND l.company_slug = p.company_slug
LEFT JOIN {{ ref('int_job_content') }} AS c
    ON p.content_hash = c.content_hash