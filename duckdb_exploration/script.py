import html
import json
import re
from pathlib import Path

import duckdb
import polars as pl

DB_PATH = Path(__file__).parent / "extracted.duckdb"


def _clean_html(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = html.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()

EXTRACTED_DIR = Path(__file__).parent.parent / "extracted"

# Nested fields whose shape varies job-to-job (dict vs list, optional keys,
# polymorphic "value" types). Kept as JSON text instead of forcing a single
# struct schema across every job/company.
JSON_TEXT_FIELDS = ("data_compliance", "departments", "metadata", "offices")


def load_jobs(directory: Path) -> pl.LazyFrame:
    frames = []
    for file in sorted(directory.glob("*.json")):
        with file.open() as f:
            payload = json.load(f)

        if "company" not in payload or "data" not in payload:
            # skip non-snapshot files, e.g. extraction_summary.json
            continue

        rows = []
        for job in payload["data"]["jobs"]:
            row = dict(job)
            row["location"] = (row.get("location") or {}).get("name")
            for field in JSON_TEXT_FIELDS:
                row[field] = json.dumps(row.get(field))
            rows.append(row)

        if not rows:
            # an empty jobs list makes pl.DataFrame([]) a (0, 0) frame, and
            # with_columns(pl.lit(...)) on that broadcasts to a bogus 1-row
            # frame instead of staying empty -- nothing to add here anyway.
            continue

        jobs = pl.DataFrame(rows, infer_schema_length=None).lazy()
        jobs = jobs.with_columns(
            pl.lit(payload["company"]).alias("company_slug"),
            pl.lit(payload["extracted_at"]).alias("extracted_at"),
        )
        frames.append(jobs)

    lf = pl.concat(frames, how="diagonal_relaxed")
    return lf.with_columns(
        pl.col("extracted_at")
        .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.f%:z")
        .dt.date()
        .alias("extracted_dt")
    )


lf = load_jobs(EXTRACTED_DIR)
lf = lf.select(
    "company_name",
    "company_slug",
    "extracted_at",
    "extracted_dt",
    "id",
    "internal_job_id",
    # "requisition_id",
    "title",
    "location",  
    # "employment",
    # "education",
    "language",
    "absolute_url",
    "content",
    "first_published",
    "updated_at",
    "application_deadline",
    # "ai_disclaimer",
    # "ai_opt_out_request_url",
    # "include_ai_disclaimer",
    # "data_compliance",
    "departments",
    "offices",
    "metadata",
)

lf = lf.with_columns(
    pl.col("location")
    .str.replace_all(r"\s*[|;]\s*", ";")
    .str.split(";")
    .alias("location")
    )

# offices: parse the JSON text back into structs and pull out just the names
# content: HTML-escaped job description -> plain text + a word count
OFFICE_DTYPE = pl.List(
    pl.Struct(
        {
            "id": pl.Int64,
            "name": pl.String,
            "location": pl.String,
            "child_ids": pl.List(pl.Int64),
            "parent_id": pl.Int64,
        }
    )
)

DEPARTMENT_DTYPE = pl.List(
    pl.Struct(
        {
            "id": pl.Int64,
            "name": pl.String,
            "child_ids": pl.List(pl.Int64),
            "parent_id": pl.Int64,
        }
    )
)

lf = lf.with_columns(
    pl.col("offices")
    .str.json_decode(OFFICE_DTYPE)
    .list.eval(pl.element().struct.field("name"))
    .alias("office_names"),

    pl.col("departments")
    .str.json_decode(DEPARTMENT_DTYPE)
    .list.eval(pl.element().struct.field("name"))
    .alias("department_names"),

    pl.col("content")
    .map_elements(_clean_html, return_dtype=pl.String)
    .alias("content_text"),
)

lf = lf.with_columns(
    pl.col("content_text").str.split(" ").list.len().alias("content_word_count"),
)

lf = lf.select(
    "company_name",
    "company_slug",
    "extracted_at",
    "extracted_dt",
    "id",
    "internal_job_id",
    "title",
    "location",
    "language",
    "absolute_url",
    "first_published",
    "updated_at",
    "application_deadline",
    # "departments",
    # "offices",
    # "metadata",
    "office_names",
    "department_names",
    "content_text",
    "content_word_count",
)

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%:z"

lf = lf.with_columns(
    pl.col("application_deadline").str.to_datetime(format=DATETIME_FORMAT, strict=False).dt.date(),
    pl.col("first_published").str.to_datetime(format=DATETIME_FORMAT, strict=False).dt.date(),
    pl.col("updated_at").str.to_datetime(format=DATETIME_FORMAT, strict=False).dt.date(),
)

df = lf.collect()
print(df.head(10))


con = duckdb.connect(str(DB_PATH))

con.execute("DROP TABLE IF EXISTS jobs")

con.execute(
    """
    CREATE TABLE IF NOT EXISTS jobs (
        company_name VARCHAR,
        company_slug VARCHAR,
        extracted_at VARCHAR,
        extracted_dt DATE,
        id BIGINT,
        internal_job_id BIGINT,
        title VARCHAR,
        location VARCHAR[],
        language VARCHAR,
        absolute_url VARCHAR,
        first_published DATE,
        updated_at DATE,
        application_deadline DATE,
        office_names VARCHAR[],
        department_names VARCHAR[],
        content_text VARCHAR,
        content_word_count UINTEGER
    )
    """
)

con.register("jobs_df", df)
con.execute("INSERT INTO jobs SELECT * FROM jobs_df")
