"""Build the national universe: every private foundation on the IRS BMF.

Private foundation = BMF foundation code 02/03/04 or a 990-PF filing
requirement. This yields ~140k EINs — the "130,000" figure the client sees
in ProPublica. (The NTEE-T category alone only covers 61k of them; 56% of
private foundations carry a non-T or blank NTEE code, so filtering by
category would silently drop most of the universe.) Writes
data/universe.csv with NTEE kept as a column.
"""

import logging
from pathlib import Path

import pandas as pd
import requests

from src.config import DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

BMF_URLS = [
    f"https://www.irs.gov/pub/irs-soi/eo{i}.csv" for i in (1, 2, 3, 4)
]
BMF_DIR = Path(DATA_DIR) / 'bmf'
UNIVERSE_CSV = Path(DATA_DIR) / 'universe.csv'

# BMF FOUNDATION codes for private foundations:
# 02/03 private operating foundation, 04 private non-operating foundation
PF_FOUNDATION_CODES = {2, 3, 4}

KEEP_COLS = ['EIN', 'NAME', 'CITY', 'STATE', 'ZIP', 'FOUNDATION',
             'NTEE_CD', 'PF_FILING_REQ_CD', 'TAX_PERIOD',
             'ASSET_AMT', 'INCOME_AMT', 'REVENUE_AMT']


def download_bmf() -> list[Path]:
    """Download the four BMF region CSVs (skips files already on disk)."""
    BMF_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for url in BMF_URLS:
        dest = BMF_DIR / url.rsplit('/', 1)[1]
        if dest.exists() and dest.stat().st_size > 0:
            log.info("%s already downloaded", dest.name)
        else:
            log.info("Downloading %s...", url)
            resp = requests.get(url, timeout=600)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            log.info("  %.1f MB", len(resp.content) / 1e6)
        paths.append(dest)
    return paths


def build_universe() -> pd.DataFrame:
    """Filter BMF to all private foundations."""
    frames = []
    for path in download_bmf():
        df = pd.read_csv(path, usecols=KEEP_COLS, dtype=str,
                         low_memory=False)
        frames.append(df)
    bmf = pd.concat(frames, ignore_index=True)
    log.info("BMF total organizations: %d", len(bmf))

    foundation = pd.to_numeric(bmf['FOUNDATION'], errors='coerce')
    pf_req = pd.to_numeric(bmf['PF_FILING_REQ_CD'], errors='coerce')
    private = bmf[
        foundation.isin(PF_FOUNDATION_CODES) | (pf_req == 1)
    ].copy()
    log.info("Private foundations (code 02/03/04 or 990-PF req): %d",
             len(private))
    ntee = private['NTEE_CD'].fillna('')
    log.info("  NTEE T: %d, other NTEE: %d, blank NTEE: %d",
             ntee.str.startswith('T').sum(),
             ((ntee != '') & ~ntee.str.startswith('T')).sum(),
             (ntee == '').sum())

    private['EIN'] = private['EIN'].str.zfill(9)
    private = private.drop_duplicates(subset='EIN')
    return private


def run():
    universe = build_universe()
    universe.to_csv(UNIVERSE_CSV, index=False)
    log.info("Wrote %d EINs to %s", len(universe), UNIVERSE_CSV)

    by_code = universe['FOUNDATION'].value_counts()
    log.info("Foundation code breakdown:\n%s", by_code.to_string())


if __name__ == '__main__':
    run()
