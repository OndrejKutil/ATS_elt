"""Extract job postings from Greenhouse job boards.

One run fetches every verified company in companies.json and writes two things:

  extracted/<timestamp>_<slug>.json  one snapshot per company
  runs/<run_id>.jsonl                one log row per company
  runs/<run_id>.meta.json            the run's terminal record

Snapshots and log rows share a run_id, which is what lets downstream models
join "what the board looked like" to "how the fetch went".
"""

import asyncio
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from tqdm.asyncio import tqdm_asyncio

COMPANIES_JSON_PATH: Path = Path("./companies.json")
EXTRACTED_DIR_PATH: Path = Path("./extracted/")
RUNS_DIR_PATH: Path = Path("./runs/")

GREENHOUSE_BOARD_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
REQUEST_TIMEOUT_SECONDS = 10


class Extractor:
    """Fetches every verified company's Greenhouse board and records the run.

    One instance runs one extraction at a time: run() stamps the run's id,
    start time and log path onto the instance, and the worker methods read
    them from there.
    """

    def __init__(
        self,
        companies_json_path: Path = COMPANIES_JSON_PATH,
        extracted_dir_path: Path = EXTRACTED_DIR_PATH,
        runs_dir_path: Path = RUNS_DIR_PATH,
    ):
        self.companies_json_path = companies_json_path
        self.extracted_dir_path = extracted_dir_path
        self.runs_dir_path = runs_dir_path

        # Guards the run log only. Every worker appends to the same file, so
        # writes must be serialised; snapshots need no lock because each
        # company writes to its own path.
        self._log_lock = threading.Lock()

        # Per-run state, set by run().
        self.run_id: str | None = None
        self.run_started_at: str | None = None
        self.run_log_path: Path | None = None

        self.runs_dir_path.mkdir(parents=True, exist_ok=True)
        self.extracted_dir_path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Company list
    # ------------------------------------------------------------------

    def _get_companies(self) -> list[str]:
        """Return the slugs of every company marked verified in companies.json.

        Unverified entries are alternative slugs kept around for retrying
        boards that did not resolve, so they are skipped here.
        """
        with open(self.companies_json_path, "r") as f:
            payload: dict = json.load(f)

        return [
            company.get("slug")
            for company in payload.get("companies")
            if company.get("verified") is True
        ]

    # ------------------------------------------------------------------
    # Fetching and writing one company's snapshot
    # ------------------------------------------------------------------

    def _fetch_sync(self, url: str) -> dict:
        """Blocking GET of one company's board. Raises on any non-200."""
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code != 200:
            raise Exception(
                f"Failed to fetch data from {url}. Status code: {response.status_code}"
            )
        return response.json()

    def _write_sync(self, result: dict, slug: str) -> None:
        """Write one company's snapshot, stamped with the current run_id."""
        # No lock: every company writes its own path, so threads never share a file.
        now = datetime.now(timezone.utc).isoformat()
        output_path = self.extracted_dir_path / f"{now}_{slug}.json"

        output = {
            "run_id": self.run_id,
            "company": slug,
            "extracted_at": now,
            "data": result,
        }

        # fsync before the log row that attests to this file: a plain write can
        # sit unwritten in memory, so on power loss the durable log row could
        # outlive the snapshot it claims exists.
        with output_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(output, indent=4))
            f.flush()
            os.fsync(f.fileno())

    # ------------------------------------------------------------------
    # Run log
    # ------------------------------------------------------------------

    def _log_row(
        self,
        slug: str,
        status: str,
        job_count: int | None,
        error: str | None,
    ) -> dict:
        """Build one run-log row.

        extracted_at is the run's start time and is identical across every row
        in a run; logged_at is when this particular company finished.
        """
        return {
            "run_id": self.run_id,
            "extracted_at": self.run_started_at,
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "slug": slug,
            "status": status,
            "job_count": job_count,
            "error": error,
        }

    def _append_run_log_line(self, row: dict) -> None:
        """Append one company's outcome, durably, the moment it is known."""
        line = json.dumps(row)
        # Locked: every worker appends to this one file, so unserialised writes
        # could interleave mid-line. fsync'd so a mid-run death still leaves the
        # rows for companies that actually finished.
        with self._log_lock:
            with self.run_log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())

    def _write_run_meta(
        self,
        expected_companies: int,
        completed: bool,
        results: list | None = None,
    ) -> None:
        """Write the run's terminal record.

        A success-only log cannot tell a failed company from a run that was cut
        off before reaching it -- absence means both. This file is the positive
        assertion of completeness: written as 'running' up front (so an aborted
        run still proves it happened and how much it intended to do), rewritten
        as 'completed' only after gather returns. A reader treats a run as whole
        only when status == 'completed' and logged_companies == expected_companies.
        """
        meta = {
            "run_id": self.run_id,
            "extracted_at": self.run_started_at,
            "expected_companies": expected_companies,
            "status": "completed" if completed else "running",
            "completed_at": datetime.now(timezone.utc).isoformat() if completed else None,
        }

        if results is not None:
            meta["logged_companies"] = len(results)
            meta["failed_companies"] = sum(1 for r in results if isinstance(r, Exception))

        # Overwrites the 'running' marker written before the run started, so
        # the file is a current-state marker rather than a history.
        (self.runs_dir_path / f"{self.run_id}.meta.json").write_text(
            json.dumps(meta, indent=4),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def _fetch_write_sync(self, url: str, slug: str) -> int:
        """Fetch, persist and log one company. Runs in a worker thread.

        The log row is written here, the instant the outcome is known, rather
        than in a batch after every company finishes -- otherwise a run that
        dies midway leaves snapshots on disk with no record they were taken.
        """
        try:
            data = self._fetch_sync(url)
            self._write_sync(data, slug)
            job_count = len(data.get("jobs") or [])
            # ok_empty means the board was read successfully and was empty --
            # a genuine "no open roles", not a failed fetch. Downstream models
            # need that distinction to infer a posting has closed.
            status = "ok" if job_count else "ok_empty"
        except Exception as exc:
            self._append_run_log_line(self._log_row(slug, "failed", None, str(exc)))
            # Re-raise so gather(return_exceptions=True) still collects it and
            # run() can report the failure.
            raise

        self._append_run_log_line(self._log_row(slug, status, job_count, None))
        return job_count

    async def run(self) -> list:
        """Run one full extraction and return the per-company results."""
        self.run_id = str(uuid.uuid4())
        self.run_started_at = datetime.now(timezone.utc).isoformat()
        self.run_log_path = self.runs_dir_path / f"{self.run_id}.jsonl"

        companies_slugs = self._get_companies()
        urls = [GREENHOUSE_BOARD_URL.format(slug=slug) for slug in companies_slugs]

        # Claim the run before doing any work, so an aborted run still leaves
        # evidence it started and how many companies it meant to cover.
        self._write_run_meta(len(companies_slugs), completed=False)

        # requests is blocking, so each company runs on its own thread.
        tasks = [
            asyncio.to_thread(self._fetch_write_sync, url, slug)
            for url, slug in zip(urls, companies_slugs)
        ]

        results = await tqdm_asyncio.gather(
            *tasks,
            desc="Extracting jobs",
            total=len(tasks),
            return_exceptions=True,
        )

        failures = [
            (slug, error)
            for slug, error in zip(companies_slugs, results)
            if isinstance(error, Exception)
        ]
        if failures:
            print(f"\n{len(failures)}/{len(tasks)} companies failed:")
            for slug, error in failures:
                print(f"  {slug}: {error}")

        # Only now is the run known to be complete.
        self._write_run_meta(len(companies_slugs), completed=True, results=results)

        return results


if __name__ == "__main__":
    asyncio.run(Extractor().run())
