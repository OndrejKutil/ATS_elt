import json
import asyncio
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from tqdm.asyncio import tqdm_asyncio

COMPANIES_JSON_PATH: Path = Path('./companies.json')
EXTRACTED_DIR_PATH: Path = Path('./extracted/')
RUNS_DIR_PATH: Path = Path('./runs/')

def _get_companies() -> list:
    with open(COMPANIES_JSON_PATH, 'r') as f:
        companies_raw: dict = json.load(f)

    companies: list = []

    companies_raw: list = companies_raw.get('companies')

    for company in companies_raw:
        if company.get('verified') is True:
            companies.append(company.get('slug'))

    return companies

def _fetch_sync(url: str):
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        raise Exception(f'Failed to fetch data from {url}. Status code: {response.status_code}')
    return response.json()

def _write_sync(result: dict, slug: str, run_id: str):
    now = datetime.now(timezone.utc).isoformat()
    output_path = EXTRACTED_DIR_PATH / f"{now}_{slug}.json"

    output = {
        "run_id": run_id,
        "company": slug,
        "extracted_at": now,
        "data": result,
    }

    output_path.write_text(
        json.dumps(output, indent=4),
        encoding="utf-8",
    )

_LOG_LOCK = threading.Lock()


def _append_run_log_line(run_log_path: Path, row: dict) -> None:
    """Append one company's outcome, durably, the moment it is known.

    Serialised across worker threads and fsync'd so a mid-run death (reboot,
    Ctrl-C, hang) leaves the rows for every company that actually finished.
    """
    line = json.dumps(row)
    with _LOG_LOCK:
        with run_log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())


def _fetch_write_sync(url: str, slug: str, run_id: str, run_started_at: str, run_log_path: Path) -> int:
    try:
        data = _fetch_sync(url)
        _write_sync(data, slug, run_id)
        job_count = len(data.get('jobs') or [])
        status = "ok" if job_count else "ok_empty"
        error = None
    except Exception as exc:
        _append_run_log_line(run_log_path, {
            "run_id": run_id,
            "extracted_at": run_started_at,
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "slug": slug,
            "status": "failed",
            "job_count": None,
            "error": str(exc),
        })
        raise

    _append_run_log_line(run_log_path, {
        "run_id": run_id,
        "extracted_at": run_started_at,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "slug": slug,
        "status": status,
        "job_count": job_count,
        "error": error,
    })
    return job_count


def _write_run_meta(run_id: str, run_started_at: str, expected_companies: int,
                    completed: bool, results: list | None = None) -> None:
    """Write the run's terminal record.

    A success-only log cannot tell a failed company from a run that was cut
    off before reaching it -- absence means both. This file is the positive
    assertion of completeness: written as 'running' up front (so an aborted
    run still proves it happened and how much it intended to do), rewritten
    as 'completed' only after gather returns. A reader treats a run as whole
    only when status == 'completed' and logged_companies == expected_companies.
    """
    meta = {
        "run_id": run_id,
        "extracted_at": run_started_at,
        "expected_companies": expected_companies,
        "status": "completed" if completed else "running",
        "completed_at": datetime.now(timezone.utc).isoformat() if completed else None,
    }

    if results is not None:
        meta["logged_companies"] = len(results)
        meta["failed_companies"] = sum(1 for r in results if isinstance(r, Exception))

    (RUNS_DIR_PATH / f"{run_id}.meta.json").write_text(
        json.dumps(meta, indent=4),
        encoding="utf-8",
    )


async def main():
    run_id = str(uuid.uuid4())
    run_started_at = datetime.now(timezone.utc).isoformat()

    companies_slugs: list = _get_companies()

    urls: list = [f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true' for slug in companies_slugs]

    EXTRACTED_DIR_PATH.mkdir(parents=True, exist_ok=True)
    RUNS_DIR_PATH.mkdir(parents=True, exist_ok=True)

    run_log_path = RUNS_DIR_PATH / f"{run_id}.jsonl"
    _write_run_meta(run_id, run_started_at, len(companies_slugs), completed=False)

    tasks: list = [
        asyncio.to_thread(_fetch_write_sync, url, slug, run_id, run_started_at, run_log_path)
        for url, slug in zip(urls, companies_slugs)
    ]

    results = await tqdm_asyncio.gather(*tasks, desc='Extracting jobs', total=len(tasks), return_exceptions=True)

    failures = [(slug, error) for slug, error in zip(companies_slugs, results) if isinstance(error, Exception)]
    if failures:
        print(f'\n{len(failures)}/{len(tasks)} companies failed:')
        for slug, error in failures:
            print(f'  {slug}: {error}')

    _write_run_meta(run_id, run_started_at, len(companies_slugs), completed=True, results=results)


if __name__ == '__main__':
    asyncio.run(main())
    