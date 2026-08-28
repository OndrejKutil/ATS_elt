-- Job posting lifecycle model.
--
-- Every extraction run drops one JSON snapshot per company into extracted/,
-- listing whatever jobs were live on that company's board at that moment.
-- A posting's lifespan is reconstructed purely from which snapshots it
-- appears in — there's no explicit "closed" event, so a posting can only be
-- inferred closed once we know a later snapshot for the same company was
-- actually a complete, successful read of the board (a run with status
-- 'ok' or 'ok_empty' in the runs table) and the posting is absent from it.
--
-- Paths are templated ({{EXTRACTED_GLOB}} / {{RUNS_GLOB}}) and substituted
-- by the Python caller with absolute globs, so this file behaves the same
-- regardless of the working directory it's invoked from.

-- One row per (snapshot, job): every posting seen in every extraction.
CREATE OR REPLACE TABLE job_snapshots AS
SELECT
    snap.company AS company_slug,
    CAST(snap.extracted_at AS TIMESTAMPTZ) AS extracted_at,
    job.id AS job_id
FROM read_json_auto('{{EXTRACTED_GLOB}}') AS snap,
     UNNEST(snap.data.jobs) AS t(job);

-- One row per company per extraction run, loaded from the run log.
CREATE OR REPLACE TABLE runs AS
SELECT
    run_id,
    slug AS company_slug,
    status,
    job_count,
    error,
    CAST(extracted_at AS TIMESTAMPTZ) AS extracted_at
FROM read_json_auto('{{RUNS_GLOB}}');

-- first_seen / last_seen per posting, plus whether it's closed: closed
-- means the company had a *successful* run (status 'ok' or 'ok_empty' —
-- both mean we got a complete read of the board, just possibly an empty
-- one) strictly after the posting's last_seen timestamp. A 'failed' run
-- proves nothing, since we never got a look at the board that time.
CREATE OR REPLACE TABLE job_lifecycle AS
WITH seen AS (
    SELECT
        company_slug,
        job_id,
        MIN(extracted_at) AS first_seen,
        MAX(extracted_at) AS last_seen
    FROM job_snapshots
    GROUP BY company_slug, job_id
)
SELECT
    seen.company_slug,
    seen.job_id,
    seen.first_seen,
    seen.last_seen,
    EXISTS (
        SELECT 1
        FROM runs
        WHERE runs.company_slug = seen.company_slug
          AND runs.status IN ('ok', 'ok_empty')
          AND runs.extracted_at > seen.last_seen
    ) AS is_closed
FROM seen;
