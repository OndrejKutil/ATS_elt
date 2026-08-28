-- One row per (run_id, company_slug): the outcome of fetching one company's
-- board in one run. status is carried through as-is from the extractor.

select
    run_id,
    slug                      as company_slug,
    status,
    job_count,
    error,
    cast(extracted_at as timestamptz) as run_started_at
from {{ source('raw', 'runs') }}
