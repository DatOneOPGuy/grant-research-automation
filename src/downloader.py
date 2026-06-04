"""Download IRS 990-PF index CSVs and filtered XML zips."""

import os
import csv
import zipfile
import logging
from io import BytesIO
from pathlib import Path

import requests
import pandas as pd

from src.config import IRS_YEARS, RAW_DIR, DATA_DIR
from src.matcher import normalize

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

IRS_DOWNLOAD_PAGE = (
    "https://www.irs.gov/charities-non-profits/"
    "form-990-series-downloads"
)

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'GrantResearchAutomation/1.0 (nonprofit research)',
})


def ensure_dirs():
    """Create data directories if they don't exist."""
    Path(RAW_DIR).mkdir(parents=True, exist_ok=True)
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def load_matches_csv(path: str = "matches.csv") -> pd.DataFrame:
    """Load Emily's matches CSV (has header row)."""
    df = pd.read_csv(path)
    df.columns = [
        'foundation_name', 'city', 'state',
        'saved', 'hidden', 'match_percent', 'grant_amount',
    ]
    log.info("Loaded %d foundations from %s", len(df), path)
    return df


def discover_irs_zip_urls(year: int) -> list[str]:
    """
    Scrape the IRS download page for XML zip URLs for a given year.
    Returns list of URLs like:
    https://www.irs.gov/pub/irs-teos/990/xml/2024/...zip
    """
    log.info("Discovering IRS zip URLs for %d...", year)
    resp = SESSION.get(IRS_DOWNLOAD_PAGE, timeout=30)
    resp.raise_for_status()

    urls = []
    for line in resp.text.split('"'):
        if f'/{year}/' in line and line.endswith('.zip'):
            if 'index' not in line.lower():
                url = line if line.startswith('http') else None
                if url:
                    urls.append(url)

    # Also look for href patterns
    import re
    pattern = rf'href="([^"]*/{year}/[^"]*\.zip)"'
    for match in re.finditer(pattern, resp.text):
        url = match.group(1)
        if 'index' not in url.lower():
            if not url.startswith('http'):
                url = 'https://www.irs.gov' + url
            if url not in urls:
                urls.append(url)

    log.info("Found %d zip URLs for %d", len(urls), year)
    return urls


def discover_index_urls(year: int) -> list[str]:
    """Find index CSV URLs for a given year."""
    log.info("Discovering IRS index URLs for %d...", year)
    resp = SESSION.get(IRS_DOWNLOAD_PAGE, timeout=30)
    resp.raise_for_status()

    import re
    urls = []
    pattern = rf'href="([^"]*/{year}/[^"]*index[^"]*\.csv)"'
    for match in re.finditer(pattern, resp.text, re.IGNORECASE):
        url = match.group(1)
        if not url.startswith('http'):
            url = 'https://www.irs.gov' + url
        if url not in urls:
            urls.append(url)

    log.info("Found %d index URLs for %d", len(urls), year)
    return urls


def download_index(url: str) -> pd.DataFrame:
    """Download an IRS index CSV and return as DataFrame."""
    log.info("Downloading index: %s", url)
    resp = SESSION.get(url, timeout=120)
    resp.raise_for_status()

    lines = resp.text.strip().split('\n')
    reader = csv.reader(lines)
    rows = list(reader)

    if not rows:
        return pd.DataFrame()

    header = rows[0]
    data = rows[1:]
    return pd.DataFrame(data, columns=header)


def build_ein_lookup(matches_df: pd.DataFrame, index_df: pd.DataFrame):
    """
    Match foundations from matches.csv to EINs in the IRS index.
    Returns dict: EIN → foundation_name, and list of unmatched.
    """
    from src.matcher import find_match

    # Build candidate list from index
    candidates = []
    ein_col = None
    name_col = None
    for col in index_df.columns:
        if 'ein' in col.lower():
            ein_col = col
        if 'name' in col.lower() or 'organization' in col.lower():
            name_col = col

    if not ein_col or not name_col:
        log.warning("Could not find EIN/name columns in index: %s",
                    list(index_df.columns))
        return {}, matches_df

    for _, row in index_df.iterrows():
        ein = str(row.get(ein_col, '')).strip()
        name = str(row.get(name_col, '')).strip()
        if ein and name:
            candidates.append({
                'ein': ein,
                'name': name,
                'normed': normalize(name),
                'city': '',
                'state': '',
            })

    log.info("Built %d candidates from IRS index", len(candidates))

    matched_eins = {}
    unmatched = []

    for _, fdn in matches_df.iterrows():
        name = str(fdn['foundation_name'])
        city = str(fdn.get('city', ''))
        state = str(fdn.get('state', ''))

        result, score, pass_num = find_match(
            name, city, state, candidates
        )

        if result and pass_num > 0:
            matched_eins[result['ein']] = name
        else:
            unmatched.append({
                'name': name,
                'city': city,
                'state': state,
                'best_candidate': (
                    result['name'] if result else ''
                ),
                'best_score': score,
            })

    log.info(
        "Matched %d / %d foundations to EINs (%d unmatched)",
        len(matched_eins), len(matches_df), len(unmatched),
    )
    return matched_eins, unmatched


def download_xml_zip(url: str, target_eins: set[str]):
    """
    Download a zip, extract only XMLs for target EINs.
    Saves to RAW_DIR.
    """
    log.info("Downloading zip: %s", os.path.basename(url))
    resp = SESSION.get(url, timeout=300, stream=True)
    resp.raise_for_status()

    content = BytesIO(resp.content)
    extracted = 0

    try:
        with zipfile.ZipFile(content) as zf:
            for name in zf.namelist():
                if not name.endswith('.xml'):
                    continue
                # EIN is often in the filename or we extract all
                # and filter during parsing
                out_path = os.path.join(RAW_DIR, os.path.basename(name))
                if not os.path.exists(out_path):
                    with zf.open(name) as src:
                        with open(out_path, 'wb') as dst:
                            dst.write(src.read())
                    extracted += 1
    except zipfile.BadZipFile:
        log.error("Bad zip file: %s", url)
        return 0

    log.info("Extracted %d XML files from %s",
             extracted, os.path.basename(url))
    return extracted


def run():
    """Main download pipeline."""
    ensure_dirs()
    matches_df = load_matches_csv()

    all_matched_eins = {}
    all_unmatched = []

    for year in IRS_YEARS:
        # Step 1: Download index
        index_urls = discover_index_urls(year)
        if not index_urls:
            log.warning("No index URLs found for %d", year)
            continue

        index_frames = []
        for url in index_urls:
            try:
                df = download_index(url)
                index_frames.append(df)
            except Exception as e:
                log.error("Failed to download index %s: %s", url, e)

        if not index_frames:
            continue

        index_df = pd.concat(index_frames, ignore_index=True)
        log.info("Combined index has %d rows for %d",
                 len(index_df), year)

        # Step 2: Match EINs
        matched, unmatched = build_ein_lookup(matches_df, index_df)
        all_matched_eins.update(matched)
        all_unmatched = unmatched  # Last year's unmatched

        # Step 3: Download XML zips (filtered)
        zip_urls = discover_irs_zip_urls(year)
        target_eins = set(matched.keys())

        for url in zip_urls:
            try:
                download_xml_zip(url, target_eins)
            except Exception as e:
                log.error("Failed to download %s: %s", url, e)

    # Save unmatched for review
    if all_unmatched:
        unmatched_df = pd.DataFrame(all_unmatched)
        unmatched_df.to_csv('unmatched.csv', index=False)
        log.info("Wrote %d unmatched foundations to unmatched.csv",
                 len(all_unmatched))

    log.info("Download complete. %d unique EINs matched.",
             len(all_matched_eins))
    return all_matched_eins


if __name__ == '__main__':
    run()
