# ATS_elt

Tracks how data-role job postings change over time across European tech companies.
Daily snapshots of public Greenhouse boards, an append-only history, and a lifecycle
model built on top of it.

Python · DuckDB · dbt · Airflow · Raspberry Pi · GCP (GCS, BigQuery) · Terraform

---

## Why this exists

Most of my experience is downstream: the data is already loaded, and I take it from
there. The part I find more interesting is upstream of that: getting data out of a source, storing
it, and keeping it trustworthy over time. That's data engineering, and it's what this
project is for.

So this is the upstream half: ingestion, raw storage, incremental state, orchestration,
cloud infrastructure, and the question of what to do when a source stops telling you
things.

The question it answers: **what do data engineering and analytics engineering roles
across European tech actually demand, and how does that change over time?** I'm applying
for these roles, so the output is something I use rather than something I maintain out of
obligation. Anything that doesn't serve that question is out of scope.

---

## Current state

| Piece                                   | Status         |
|-----------------------------------------|----------------|
| Extractor (Greenhouse → gzipped JSON)   | done           |
| dbt on DuckDB: staging + intermediate   | done           |
| Airflow on the Pi, daily at 07:00       | done           |
| GCP infra via Terraform                 | done           |
| Raw snapshots landing in GCS            | in progress    |
| dbt on BigQuery                         | in progress    |
| Mart (`marts_job_postings`)             | done           |

Right now the whole pipeline runs locally on a Raspberry Pi: Airflow triggers the
extractor, which writes to local disk, then `dbt build` runs against a DuckDB file.

The next step is moving storage and the warehouse to GCP. Terraform already provisions:

- a GCS bucket (`{project_id}-raw`) for the raw snapshot archive
- a BigQuery dataset (`ats`)
- an `ats-pipeline` service account for the Pi, with write access to the bucket, the
  dataset, and permission to run BigQuery jobs

What's still left is pointing the extractor at the bucket and adding a BigQuery target
to dbt, with the sources reading from GCS instead of local files.

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
├── companies.json                  seed list: slug, verified flag
├── pyproject.toml
│
├── dags/
│   ├── run_extractor.py            Airflow DAG: extractor >> dbt build, daily 07:00 Prague
│   └── python/
│       └── extractor.py            fetch every verified board, write snapshots + run log
│
├── deploy/
│   └── airflow@.service            systemd unit for Airflow (scheduler, api-server, ...)
│
├── infra/
│   └── main.tf                     Terraform: GCS bucket, BigQuery dataset, service account
│
├── data/                           extractor output (gitignored)
│   ├── extracted/                  raw archive
│   │   └── dt=YYYY-MM-DD/
│   │       └── {slug}__{run_id}.json.gz
│   └── runs/                       run log
│       ├── {run_id}.jsonl          one line per company: status, job_count, error
│       └── {run_id}.meta.json      terminal record: did the run finish, and how far
│
└── dbt/
    ├── dbt_project.yml
    ├── profiles.yml                kept in-project, not ~/.dbt
    ├── packages.yml
    ├── ats.duckdb                  the warehouse (gitignored)
    ├── macros/
    │   ├── job_content_hash.sql    the one definition of "same posting content"
    │   ├── split_locations.sql     the one definition of how location strings split
    │   ├── strip_html.sql
    │   └── html_unescape.sql
    └── models/
        ├── staging/
        │   ├── _sources.yml        reads the files directly via read_json_auto
        │   ├── _models.yml         schema tests
        │   ├── stg_run_log.sql
        │   ├── stg_job_snapshots.sql
        │   └── stg_job_content.sql
        ├── intermediate/
        │   ├── int_job_content.sql
        │   └── int_job_lifecycle.sql
        └── marts/
            └── marts_job_postings.sql
```

---

## Running it

Manually:

```bash
uv run dags/python/extractor.py           # fetch boards, write snapshots + run log

export DBT_PROFILES_DIR=/home/pi/ATS_elt/dbt
cd dbt
uv run dbt deps
uv run dbt build
```

On the Pi, Airflow runs the same two steps as the `run_ext_and_dbt_build` DAG every day
at 07:00 (Europe/Prague). Airflow components run as systemd services from
`deploy/airflow@.service`, e.g. `systemctl enable --now airflow@scheduler`.

Reading the warehouse (`-readonly` avoids fighting dbt for the write lock):

```bash
duckdb -readonly dbt/ats.duckdb
```

Provisioning the GCP side:

```bash
cd infra
terraform init
terraform apply -var="project_id=<your-gcp-project>"
```
