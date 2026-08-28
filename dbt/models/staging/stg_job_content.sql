{{
    config(
        materialized='incremental',
        incremental_strategy='delete+insert',
        unique_key='content_hash',
    )
}}

-- One row per distinct content_hash: the posting body, stored once no matter
-- how many runs observed it. This is where the ~40x duplication of the body is
-- collapsed -- stg_job_snapshots keeps only the hash.
--
-- Insert-only: a hash's body is by definition identical every time it is seen,
-- so an existing row is never updated. first_seen_dt is the partition the hash
-- was first observed in, and doubles as the incremental watermark.

WITH unnested AS (

    SELECT
        snap.dt,
        unnest(snap.data.jobs) AS job
    FROM {{ source('raw', 'snapshots') }} AS snap

    {% if is_incremental() %}
    -- Filter on dt, not on extracted_at: dt is a Hive partition column, so
    -- DuckDB skips whole directories without opening the files inside them.
    -- An equivalent timestamp filter would still read every file to evaluate.
    WHERE snap.dt > (SELECT max(first_seen_dt) FROM {{ this }})
    {% endif %}

),

hashed AS (

    SELECT
        {{ job_content_hash('job') }} AS content_hash,
        dt                            AS first_seen_dt,
        job.content                   AS content,
        -- Names only, sorted, matching what job_content_hash() hashes: rows
        -- sharing a hash therefore hold identical arrays here.
        list_sort(list_transform(job.departments, x -> x.name)) AS departments,
        list_sort(list_transform(job.offices, x -> x.name))     AS offices
    FROM unnested

)

SELECT
    content_hash,
    min(first_seen_dt)     AS first_seen_dt,
    -- The hash collapses whitespace, so bodies in a group can differ in
    -- whitespace alone; min() picks one deterministically rather than
    -- arbitrarily. departments/offices are identical within a group.
    min(content)           AS content,
    any_value(departments) AS departments,
    any_value(offices)     AS offices
FROM hashed
{% if is_incremental() %}
WHERE content_hash NOT IN (SELECT content_hash FROM {{ this }})
{% endif %}
GROUP BY content_hash
