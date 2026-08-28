-- One row per (run_id, company_slug, job_id): a posting as it appeared on a
-- company's board in one extraction run. The whole job object is kept in
-- raw_job so downstream models can reach fields this model does not type.

with unnested as (

    select
        snap.run_id,
        snap.company                          as company_slug,
        cast(snap.extracted_at as timestamptz) as extracted_at,
        unnest(snap.data.jobs)                as job
    from {{ source('raw', 'snapshots') }} as snap

)

select
    run_id,
    company_slug,
    extracted_at,
    job.id                                as job_id,
    job.title                             as title,
    job.location.name                     as location,
    cast(job.updated_at as timestamptz)      as updated_at,
    cast(job.first_published as timestamptz) as first_published,
    to_json(job)                          as raw_job
from unnested
