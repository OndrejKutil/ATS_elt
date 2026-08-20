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
    try:
        response = requests.get(url, timeout=10)
        return response.status_code, response.json()
    except requests.RequestException as e:
        print(f'Error fetching {url}: {e}')
        raise

def _write_sync(result: dict, slug: str):
    output_path = EXTRACTED_DIR_PATH / f"{slug}.json"

    try:
        output = {
            "company": slug,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "data": result,
        }

        EXTRACTED_DIR_PATH.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output, indent=4),
            encoding="utf-8",
        )
    except Exception as e:
        print(f'Error writing data to {output_path}: {e}')
        raise

def _fetch_write_sync(url: str, slug: str):
    status_code, data = _fetch_sync(url)
    if status_code == 200:
        _write_sync(data, slug)
    else:
        raise Exception(f'Failed to fetch data from {url}. Status code: {status_code}')


async def main():
    companies_slugs: list = _get_companies()

    urls: list = [f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true' for slug in companies_slugs]

    tasks = [asyncio.to_thread(_fetch_write_sync, url, slug) for url, slug in zip(urls, companies_slugs)]
    
    await tqdm_asyncio.gather(*tasks, desc='Extracting jobs', total=len(tasks))


if __name__ == '__main__':
    asyncio.run(main())
    