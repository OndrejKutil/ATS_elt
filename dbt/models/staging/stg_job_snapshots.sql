{{
    config(
        materialized='incremental',
        incremental_strategy='delete+insert',
        unique_key='dt',
    )
}}

-- One row per (run_id, company_slug, job_id): a posting as it appeared on a
-- company's board in one extraction run.
--
-- The job body is deliberately not stored here. At ~15k postings per run and a
-- ~40 day average lifetime, the same content HTML would be rewritten ~40 times
-- per posting. Instead this model carries content_hash, and the body lives once
-- per distinct hash in stg_job_content.

WITH unnested AS (

    SELECT
        snap.run_id,
        snap.company                           AS company_slug,
        snap.dt,
        CAST(snap.extracted_at AS TIMESTAMPTZ) AS extracted_at,
        unnest(snap.data.jobs)                 AS job
    FROM {{ source('raw', 'snapshots') }} AS snap

    {% if is_incremental() %}
    -- Filter on dt, not on extracted_at: dt is a Hive partition column, so
    -- DuckDB skips whole directories without opening the files inside them.
    -- An equivalent timestamp filter would still read every file to evaluate.
    WHERE snap.dt > (SELECT max(dt) FROM {{ this }})
    {% endif %}

)

SELECT
    run_id,
    company_slug,
    dt,
    extracted_at,
    job.company_name                         AS company_name,
    job.absolute_url                         AS absolute_url,
    job.employment                           AS employment,
    job.language                             AS language,
    job.id                                   AS job_id,
    job.title                                AS title,
    -- location.name can pack several locations into one string; split on the
    -- delimiters so downstream can unnest rather than pattern-match.
    {{ split_locations('job.location.name') }} AS location,
    CAST(job.updated_at AS TIMESTAMPTZ)      AS updated_at,
    CAST(job.first_published AS TIMESTAMPTZ) AS first_published,
    {{ job_content_hash('job') }}            AS content_hash
FROM unnested
