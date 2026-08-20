import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path

import requests
from tqdm.asyncio import tqdm_asyncio

COMPANIES_JSON_PATH: Path = Path('./companies.json')
EXTRACTED_DIR_PATH: Path = Path('./extracted/')

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

def _write_sync(result: dict, slug: str):
    now = datetime.now(timezone.utc).isoformat()
    output_path = EXTRACTED_DIR_PATH / f"{now}_{slug}.json"

    output = {
        "company": slug,
        "extracted_at": now,
        "data": result,
    }

    output_path.write_text(
        json.dumps(output, indent=4),
        encoding="utf-8",
    )

def _fetch_write_sync(url: str, slug: str):
    data = _fetch_sync(url)
    _write_sync(data, slug)


async def main():
    companies_slugs: list = _get_companies()

    urls: list = [f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true' for slug in companies_slugs]

    EXTRACTED_DIR_PATH.mkdir(parents=True, exist_ok=True)

    tasks: list = [asyncio.to_thread(_fetch_write_sync, url, slug) for url, slug in zip(urls, companies_slugs)]

    results = await tqdm_asyncio.gather(*tasks, desc='Extracting jobs', total=len(tasks), return_exceptions=True)

    failures = [(slug, error) for slug, error in zip(companies_slugs, results) if isinstance(error, Exception)]
    if failures:
        print(f'\n{len(failures)}/{len(tasks)} companies failed:')
        for slug, error in failures:
            print(f'  {slug}: {error}')


if __name__ == '__main__':
    asyncio.run(main())
    