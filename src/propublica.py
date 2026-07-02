"""ProPublica Nonprofit Explorer gap-filler.

Per-EIN org lookups for universe foundations with no e-file XML (paper
filers). Throttled to ~1 request/sec, cached to disk so re-runs are free.
The API exposes no phone/website; we take name/address/NTEE and the
latest available filing's total revenue.
"""

import json
import logging
import time
from pathlib import Path

import requests

from src.config import DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

API_URL = ("https://projects.propublica.org/nonprofits/api/v2/"
           "organizations/{ein}.json")
CACHE_DIR = Path(DATA_DIR) / 'propublica_cache'
MISSING_EINS = Path(DATA_DIR) / 'universe_missing_eins.txt'
OUTPUT_CSV = Path(DATA_DIR) / 'propublica_gapfill.csv'
THROTTLE_SECONDS = 1.0

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'GrantResearchAutomation/1.0 (nonprofit research)',
})


def fetch_org(ein: str) -> dict | None:
    """Fetch one org from ProPublica, disk-cached. None if not found."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{ein}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    resp = SESSION.get(API_URL.format(ein=int(ein)), timeout=30)
    time.sleep(THROTTLE_SECONDS)
    if resp.status_code == 404:
        cache_file.write_text('null')
        return None
    resp.raise_for_status()
    data = resp.json()
    cache_file.write_text(json.dumps(data))
    return data


def summarize(ein: str, data: dict | None) -> dict:
    row = {'ein': ein, 'propublica_found': 'No', 'name': '',
           'city': '', 'state': '', 'ntee_code': '',
           'latest_pf_filing': '', 'latest_revenue': ''}
    if not data or not data.get('organization'):
        return row
    org = data['organization']
    row.update({
        'propublica_found': 'Yes',
        'name': org.get('name') or '',
        'city': org.get('city') or '',
        'state': org.get('state') or '',
        'ntee_code': org.get('ntee_code') or '',
    })
    pf_filings = [f for f in data.get('filings_with_data', [])
                  if f.get('formtype') == 2]
    if pf_filings:
        latest = max(pf_filings, key=lambda f: f.get('tax_prd') or 0)
        row['latest_pf_filing'] = latest.get('tax_prd') or ''
        row['latest_revenue'] = latest.get('totrevenue') or ''
    return row


def run(limit: int | None = None):
    eins = [e.strip() for e in MISSING_EINS.read_text().splitlines()
            if e.strip()]
    if limit:
        eins = eins[:limit]
    log.info("Gap-filling %d EINs via ProPublica (throttled 1 req/s)...",
             len(eins))

    rows, errors = [], 0
    for i, ein in enumerate(eins, 1):
        try:
            rows.append(summarize(ein, fetch_org(ein)))
        except Exception as e:
            errors += 1
            log.warning("EIN %s failed: %s", ein, e)
            if errors > 20:
                log.error("Too many errors; stopping at %d/%d",
                          i, len(eins))
                break
        if i % 500 == 0:
            log.info("  %d / %d", i, len(eins))

    import pandas as pd
    pd.DataFrame(rows).to_csv(OUTPUT_CSV, index=False)
    found = sum(1 for r in rows if r['propublica_found'] == 'Yes')
    log.info("Wrote %s: %d looked up, %d found on ProPublica",
             OUTPUT_CSV, len(rows), found)


if __name__ == '__main__':
    import sys
    limit = int(sys.argv[sys.argv.index('--limit') + 1]) \
        if '--limit' in sys.argv else None
    run(limit)
