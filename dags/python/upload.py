"""Sync local extractor output to GCS. Idempotent: uploads only what's missing or changed."""

import base64
import hashlib
import sys
from pathlib import Path

from google.cloud import storage

REPO_ROOT = Path(__file__).resolve().parents[2]   # adjust if file moves
DATA_DIR = REPO_ROOT / "data"
BUCKET = "ats-elt-raw"
PROJECT = "ats-elt"

PATTERNS = ["extracted/**/*.json.gz", "runs/*.jsonl", "runs/*.meta.json"]


def local_files() -> list[str]:
    files = []
    for pattern in PATTERNS:
        for path in DATA_DIR.glob(pattern):
            files.append(path.relative_to(DATA_DIR).as_posix())
    return files


def local_md5(path: Path) -> str:                              
    """MD5 in the same format GCS reports it: base64 of the raw digest."""
    return base64.b64encode(hashlib.md5(path.read_bytes()).digest()).decode()


def main() -> int:
    client = storage.Client(project=PROJECT)
    bucket = client.bucket(BUCKET)

    # name -> MD5, instead of just names     
    existing = {blob.name: blob.md5_hash for blob in bucket.list_blobs()}

    uploaded, skipped, failed = 0, 0, []

    for path in local_files():
        if path in existing:                                     
            # Snapshots and run logs are write-once: same name = same file.
            # Meta files are rewritten (running -> completed), so compare content.
            is_meta = path.endswith(".meta.json")
            if not is_meta or existing[path] == local_md5(DATA_DIR / path):
                skipped += 1
                continue

        try:
            bucket.blob(path).upload_from_filename(DATA_DIR / path)
            uploaded += 1
        except Exception as e:
            failed.append((path, str(e)))

    print(f"Uploaded: {uploaded}, Skipped: {skipped}, Failed: {len(failed)}")
    if failed:
        print("Failed uploads:")
        for path, error in failed:
            print(f"  {path}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())