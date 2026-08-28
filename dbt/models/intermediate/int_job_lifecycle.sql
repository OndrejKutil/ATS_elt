-- int_job_lifecycle
--
-- first_seen / last_seen per posting, and whether it has closed.
--
-- Closure cannot be read off the snapshots alone: a posting missing from a run
-- might have been withdrawn, or the fetch for that company might simply have
-- failed. So is_closed asks the run log whether a *later* run actually
-- observed this company's board -- status 'ok' or 'ok_empty' (an empty board
-- is a real observation; a 'failed' fetch is not).

WITH lifecycle AS (

    SELECT
        job_id,
        any_value(company_slug) AS company_slug,
        min(dt) AS first_seen,
        max(dt) AS last_seen
    FROM {{ ref('stg_job_snapshots') }}
    GROUP BY 1

)

SELECT
    l.job_id,
    l.company_slug,
    l.first_seen,
    l.last_seen,

    EXISTS (
        SELECT 1
        FROM {{ ref('stg_run_log') }} AS r
        WHERE r.company_slug = l.company_slug
          AND r.status IN ('ok', 'ok_empty')
          AND CAST(r.run_started_at AT TIME ZONE 'UTC' AS DATE) > l.last_seen
    ) AS is_closed

FROM lifecycle AS l
