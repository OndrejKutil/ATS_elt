-- One row per (run_id, company_slug): the outcome of fetching one company's
-- board in one run. status is carried through as-is from the extractor.

SELECT
    run_id,
    slug                              AS company_slug,
    status,
    job_count,
    error,
    CAST(extracted_at AS TIMESTAMPTZ) AS run_started_at
FROM {{ source('raw', 'runs') }}
