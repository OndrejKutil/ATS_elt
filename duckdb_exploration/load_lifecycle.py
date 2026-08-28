from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent / "extracted.duckdb"
EXTRACTED_DIR = Path(__file__).parent.parent / "extracted"
RUNS_DIR = Path(__file__).parent.parent / "runs"
LIFECYCLE_SQL_PATH = Path(__file__).parent / "sql" / "lifecycle.sql"


def run(con: duckdb.DuckDBPyConnection) -> None:
    sql = LIFECYCLE_SQL_PATH.read_text()
    sql = sql.replace("{{EXTRACTED_GLOB}}", str(EXTRACTED_DIR / "*.json"))
    sql = sql.replace("{{RUNS_GLOB}}", str(RUNS_DIR / "*.jsonl"))
    con.execute(sql)


if __name__ == "__main__":
    if not any(RUNS_DIR.glob("*.jsonl")):
        raise SystemExit(
            f"No run logs found in {RUNS_DIR}. Run extractor.py at least once "
            "(it now writes runs/<run_id>.jsonl) before building the lifecycle model."
        )

    con = duckdb.connect(str(DB_PATH))
    run(con)

    for table in ("job_snapshots", "runs", "job_lifecycle"):
        count = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")
