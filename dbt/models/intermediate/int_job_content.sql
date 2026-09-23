-- int_job_content
--
-- The posting body as plain text, one row per distinct content_hash.
--
-- stg_job_content holds what Greenhouse returned: an HTML fragment, entity-
-- escaped twice. Nothing downstream wants that, and every consumer that has to
-- undo it would undo it slightly differently -- so it is undone once, here.
-- strip_html() is the single definition of how; see the macro for the stages.
--
-- The raw body is deliberately not carried forward. It is a large column, it
-- is already stored once per hash in staging, and a consumer that genuinely
-- needs the markup can join back on content_hash.
--
-- Materialised as a table rather than a view: the cleaning is ~30 regex passes
-- over a multi-kilobyte string, so paying for it once per hash beats paying
-- for it on every downstream scan.

{{ config(materialized='table') }}

WITH cleaned AS (

    SELECT
        content_hash,
        first_seen_dt,
        departments,
        offices,
        {{ strip_html('content') }} AS content_text
    FROM {{ ref('stg_job_content') }}

)

SELECT
    content_hash,
    first_seen_dt,
    departments,
    offices,
    content_text,
    length(content_text)                       AS content_char_count,
    -- Cheap proxy for length that survives reformatting, for downstream
    -- filtering of stub postings ("apply here", and nothing else).
    len(str_split_regex(trim(content_text), '\s+')) AS content_word_count
FROM cleaned
