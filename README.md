# ATS_elt

Tracks how data-role job postings change over time across European tech companies.
Daily snapshots of public Greenhouse boards, an append-only history, and a lifecycle
model built on top of it.

Python · DuckDB · dbt · Raspberry Pi

---

## Why this exists

I own a transformation layer professionally — a layered dbt project on production data,
staging through marts, and I'm accountable for its correctness. What I had never built is
everything upstream of it: the raw data arrives already loaded.

So this is the upstream half, built deliberately. Ingestion, raw storage, incremental
state, and the question of what to do when a source stops telling you things.

The question it answers: **what do data engineering and analytics engineering roles
across European tech actually demand, and how does that change over time?** I'm applying
for these roles, so the output is something I use rather than something I maintain out of
obligation. Anything that doesn't serve that question is out of scope.

---

## Source

Public Greenhouse job boards, one endpoint per company, no auth and no pagination:

```
https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
```

There is no directory of Greenhouse boards, so `companies.json` is a hand-built seed
list: 160 candidate slugs, 60 confirmed live.

---

## Project structure

```
ATS_elt/
├── extractor.py                    fetch every verified board, write snapshots + run log
├── companies.json                  seed list: slug, verified flag
├── pyproject.toml
│
├── extracted/                      raw archive (gitignored)
│   └── dt=YYYY-MM-DD/
│       └── {slug}__{run_id}.json.gz
│
├── runs/                           run log (gitignored)
│   ├── {run_id}.jsonl              one line per company: status, job_count, error
│   └── {run_id}.meta.json          terminal record: did the run finish, and how far
│
└── dbt/
    ├── dbt_project.yml
    ├── profiles.yml                kept in-project, not ~/.dbt
    ├── packages.yml
    ├── ats.duckdb                  the warehouse (gitignored)
    ├── macros/
    │   ├── job_content_hash.sql    the one definition of "same posting content"
    │   └── split_locations.sql     the one definition of how location strings split
    └── models/
        ├── staging/
        │   ├── _sources.yml        reads the files directly via read_json_auto
        │   ├── _models.yml         schema tests
        │   ├── stg_run_log.sql
        │   ├── stg_job_snapshots.sql
        │   └── stg_job_content.sql
        ├── intermediate/
        │   └── int_job_lifecycle.sql
        └── marts/
            └── fct_job_postings.sql    stub, not implemented
```

---

## Running it

```bash
uv run extractor.py                       # fetch boards, write snapshots + run log

export DBT_PROFILES_DIR=/home/pi/ATS_elt/dbt
cd dbt
uv run dbt deps
uv run dbt build
```

Reading the warehouse (`-readonly` avoids fighting dbt for the write lock):

```bash
duckdb -readonly dbt/ats.duckdb
```
