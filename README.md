# ATS ELT

Extracts job postings from Greenhouse job boards and models them with dbt + DuckDB.

## Pipeline

1. `uv run extractor.py` — fetches every verified company in `companies.json` and writes:
   - `extracted/<timestamp>_<slug>.json` — one snapshot per company per run
   - `runs/<run_id>.jsonl` — the run log, one line per company, **appended as each
     company finishes** so a run killed midway still leaves rows for the work it did
   - `runs/<run_id>.meta.json` — the run's terminal record (see below)
2. `dbt build` — reads those files directly from disk via DuckDB.

### Run completeness

A log that only records successes cannot distinguish a company that *failed* from a
run that was *cut off before reaching it* — absence means both. So each run also
writes `runs/<run_id>.meta.json`: `status: "running"` up front, rewritten to
`status: "completed"` with `logged_companies` / `expected_companies` after the run
finishes. Treat a run as whole only when `status == "completed"` and
`logged_companies == expected_companies`. The `runs/*.jsonl` glob deliberately
excludes these `.meta.json` files.

## dbt

The project lives in `dbt/`, with `profiles.yml` kept **inside the project** rather
than `~/.dbt`. Point dbt at it with `DBT_PROFILES_DIR`:

```bash
export DBT_PROFILES_DIR=/home/pi/ATS_elt/dbt
cd dbt
uv run dbt deps
uv run dbt build
```

Or per-command without exporting:

```bash
uv run dbt build --profiles-dir /home/pi/ATS_elt/dbt
```

Target `dev` writes to `dbt/ats.duckdb`.

Raw file paths are absolute so runs do not depend on the invocation directory. They
default to the `ats_root` var in `dbt_project.yml`; override with the `ATS_ROOT`
environment variable to point dbt at a different checkout:

```bash
ATS_ROOT=/some/other/checkout uv run dbt build
```

### Models

- `staging/stg_run_log` — one row per `(run_id, company_slug)`, status as-is
- `staging/stg_job_snapshots` — one row per `(run_id, company_slug, job_id)`,
  unnested from `data.jobs`, with the full job object kept as `raw_job`
- `intermediate/int_job_lifecycle`, `marts/fct_job_postings` — stubs, not
  implemented, disabled in `dbt_project.yml`

`duckdb_exploration/` is throwaway exploration, not part of the dbt pipeline.
