"""Download 990-PF XMLs for the full private-foundation universe.

Pipeline: refresh IRS e-file indexes (2023-2025) -> filter to 990-PF
filings by universe EINs -> stream TEOS zips extracting only those
filings. Resumable; skips files already in data/raw.
"""

import logging
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR, IRS_YEARS, RAW_DIR
from src.downloader import (
    discover_index_urls, discover_irs_zip_urls, download_index,
)
from src.download_xmls import extract_from_zip

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

UNIVERSE_CSV = Path(DATA_DIR) / 'universe.csv'
PF_INDEX_CSV = Path(DATA_DIR) / 'pf_index_universe.csv'
MISSING_EINS = Path(DATA_DIR) / 'universe_missing_eins.txt'


def refresh_pf_index() -> pd.DataFrame:
    """Download indexes for all configured years; keep 990-PF rows."""
    frames = []
    for year in IRS_YEARS:
        for url in discover_index_urls(year):
            try:
                df = download_index(url)
            except Exception as e:
                log.error("Index %s failed: %s", url, e)
                continue
            if len(df):
                df['index_year'] = year
                frames.append(df)
    index = pd.concat(frames, ignore_index=True)
    pf = index[index['RETURN_TYPE'] == '990PF'].copy()
    pf['EIN'] = pf['EIN'].astype(str).str.zfill(9)
    pf = pf.drop_duplicates(subset='OBJECT_ID')
    log.info("Index rows: %d total, %d unique 990-PF", len(index), len(pf))
    return pf


def build_targets() -> tuple[set[str], pd.DataFrame]:
    """Intersect the 990-PF index with universe EINs."""
    universe = pd.read_csv(UNIVERSE_CSV, dtype=str)
    universe_eins = set(universe['EIN'].str.zfill(9))

    pf = refresh_pf_index()
    targets = pf[pf['EIN'].isin(universe_eins)].copy()
    targets.to_csv(PF_INDEX_CSV, index=False)

    covered = set(targets['EIN'])
    missing = universe_eins - covered
    MISSING_EINS.write_text('\n'.join(sorted(missing)) + '\n')
    log.info(
        "Universe %d EINs: %d with e-file filings (%d filings), "
        "%d missing (paper filers / not yet filed) -> %s",
        len(universe_eins), len(covered), len(targets),
        len(missing), MISSING_EINS,
    )
    return set(targets['OBJECT_ID'].astype(str)), targets


def download_filings(target_objects: set[str]):
    """Stream every year's zips, extracting target filings."""
    Path(RAW_DIR).mkdir(parents=True, exist_ok=True)
    on_disk = {p.stem.replace('_public', '')
               for p in Path(RAW_DIR).glob('*.xml')}
    needed = target_objects - on_disk
    log.info("%d target filings, %d already on disk, %d to fetch",
             len(target_objects), len(target_objects) - len(needed),
             len(needed))
    if not needed:
        return

    for year in IRS_YEARS:
        for url in discover_irs_zip_urls(year):
            try:
                extract_from_zip(url, target_objects)
            except Exception as e:
                log.error("Zip %s failed: %s", url, e)

    now_on_disk = {p.stem.replace('_public', '')
                   for p in Path(RAW_DIR).glob('*.xml')}
    still_missing = target_objects - now_on_disk
    log.info("Download pass done: %d/%d targets on disk (%d missing)",
             len(target_objects) - len(still_missing),
             len(target_objects), len(still_missing))


def run(download: bool = True):
    target_objects, _ = build_targets()
    if download:
        download_filings(target_objects)


if __name__ == '__main__':
    import sys
    run(download='--targets-only' not in sys.argv)
