"""Download IRS 990 XML zips and extract only our target filings."""

import os
import zipfile
import logging
import time
from io import BytesIO
from pathlib import Path

import requests
import pandas as pd

from src.config import RAW_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'GrantResearchAutomation/1.0 (nonprofit research)',
})

ZIP_URLS = {
    2023: [
        f"https://apps.irs.gov/pub/epostcard/990/xml/2023/"
        f"2023_TEOS_XML_{m}.zip"
        for m in [
            '01A', '02A', '03A', '04A', '05A', '06A',
            '07A', '08A', '09A', '10A', '11A', '12A',
        ]
    ],
    2024: [
        f"https://apps.irs.gov/pub/epostcard/990/xml/2024/"
        f"2024_TEOS_XML_{m}.zip"
        for m in [
            '01A', '02A', '03A', '04A', '05A', '06A',
            '07A', '08A', '09A', '10A', '11A', '12A',
        ]
    ],
}


def load_target_objects() -> set[str]:
    """Load target OBJECT_IDs from file."""
    path = 'data/target_objects.txt'
    with open(path) as f:
        targets = set(line.strip() for line in f if line.strip())
    log.info("Loaded %d target OBJECT_IDs", len(targets))
    return targets


def load_target_eins() -> set[str]:
    """Load target EINs from file."""
    path = 'data/target_eins.txt'
    with open(path) as f:
        eins = set(line.strip() for line in f if line.strip())
    log.info("Loaded %d target EINs", len(eins))
    return eins


def extract_from_zip(url, target_objects):
    """
    Download a zip and extract only XML files matching target OBJECT_IDs.
    Returns (extracted_count, skipped_count, bytes_written).
    """
    zip_name = os.path.basename(url)
    log.info("Downloading %s...", zip_name)

    start = time.time()
    resp = SESSION.get(url, timeout=600, stream=True)
    resp.raise_for_status()

    content = BytesIO(resp.content)
    download_mb = len(resp.content) / (1024 * 1024)
    dl_time = time.time() - start
    log.info("  Downloaded %.0f MB in %.0fs", download_mb, dl_time)

    extracted = 0
    skipped = 0
    bytes_written = 0

    try:
        with zipfile.ZipFile(content) as zf:
            names = zf.namelist()
            log.info("  Zip contains %d files", len(names))

            for name in names:
                if not name.endswith('.xml'):
                    continue

                # Extract OBJECT_ID from filename
                # Format: {OBJECT_ID}_public.xml
                basename = os.path.basename(name)
                obj_id = basename.replace('_public.xml', '')

                if obj_id not in target_objects:
                    skipped += 1
                    continue

                out_path = os.path.join(RAW_DIR, basename)
                if os.path.exists(out_path):
                    extracted += 1  # Already downloaded
                    continue

                with zf.open(name) as src:
                    data = src.read()
                    with open(out_path, 'wb') as dst:
                        dst.write(data)
                    bytes_written += len(data)
                    extracted += 1

    except zipfile.BadZipFile:
        log.error("  Bad zip file: %s", zip_name)
        return 0, 0, 0

    log.info(
        "  Extracted %d target XMLs, skipped %d, wrote %.1f MB",
        extracted, skipped, bytes_written / (1024 * 1024),
    )
    return extracted, skipped, bytes_written


def find_missing_eins(target_eins):
    """Check which target EINs have no XML file on disk."""
    # Load index to map EIN -> OBJECT_ID
    full_index = pd.read_csv('data/full_index.csv', low_memory=False)
    matched = full_index[
        full_index['EIN'].astype(str).isin(target_eins)
    ].copy()

    # Check which OBJECT_IDs we actually have on disk
    on_disk = set()
    for f in Path(RAW_DIR).glob('*.xml'):
        obj_id = f.stem.replace('_public', '')
        on_disk.add(obj_id)

    # For each EIN, check if at least one of its filings is on disk
    ein_has_filing = set()
    ein_missing_years = {}

    for _, row in matched.iterrows():
        ein = str(row['EIN'])
        obj_id = str(row['OBJECT_ID'])
        sub_year = str(row['SUB_DATE'])[:4]

        if obj_id in on_disk:
            ein_has_filing.add(ein)
        else:
            if ein not in ein_missing_years:
                ein_missing_years[ein] = []
            ein_missing_years[ein].append(sub_year)

    # EINs with NO filing at all on disk
    completely_missing = target_eins - ein_has_filing
    return completely_missing, ein_missing_years


def run():
    """Download all zips and extract target filings."""
    Path(RAW_DIR).mkdir(parents=True, exist_ok=True)

    target_objects = load_target_objects()
    target_eins = load_target_eins()

    total_extracted = 0
    total_skipped = 0
    total_bytes = 0
    all_urls = ZIP_URLS[2023] + ZIP_URLS[2024]

    log.info("=" * 60)
    log.info("Starting download of %d zip files", len(all_urls))
    log.info("Looking for %d target filings across %d EINs",
             len(target_objects), len(target_eins))
    log.info("=" * 60)

    start_all = time.time()

    for i, url in enumerate(all_urls):
        log.info("\n[%d/%d] %s", i + 1, len(all_urls),
                 os.path.basename(url))
        try:
            extracted, skipped, bytes_w = extract_from_zip(
                url, target_objects
            )
            total_extracted += extracted
            total_skipped += skipped
            total_bytes += bytes_w
        except Exception as e:
            log.error("Failed to process %s: %s", url, e)

    elapsed = time.time() - start_all

    # Count actual files on disk
    xml_files = list(Path(RAW_DIR).glob('*.xml'))
    disk_size = sum(f.stat().st_size for f in xml_files)

    # Find missing EINs
    missing_eins, ein_missing_years = find_missing_eins(target_eins)

    # === FINAL REPORT ===
    log.info("\n" + "=" * 60)
    log.info("DOWNLOAD COMPLETE")
    log.info("=" * 60)
    log.info("Total XML files downloaded: %d", len(xml_files))
    log.info("Total size on disk: %.1f MB (%.2f GB)",
             disk_size / (1024 * 1024),
             disk_size / (1024 * 1024 * 1024))
    log.info("Total download time: %.0fs (%.1f min)",
             elapsed, elapsed / 60)
    log.info("")
    log.info("EINs with at least one filing: %d / %d",
             len(target_eins) - len(missing_eins),
             len(target_eins))
    log.info("EINs with NO XML filing found: %d", len(missing_eins))

    if missing_eins:
        # Save missing EINs to file
        missing_path = 'data/missing_eins.txt'
        with open(missing_path, 'w') as f:
            for ein in sorted(missing_eins):
                f.write(ein + '\n')
        log.info("Missing EINs saved to %s", missing_path)

        # Show first 20
        log.info("\nSample missing EINs (first 20):")
        ein_index = pd.read_csv(
            'data/ein_mapping.csv', low_memory=False
        )
        for ein in sorted(missing_eins)[:20]:
            name_row = ein_index[
                ein_index['ein'].astype(str) == ein
            ]
            name = (name_row.iloc[0]['irs_name']
                    if len(name_row) > 0 else 'UNKNOWN')
            log.info("  EIN %s: %s", ein, name)

    log.info("=" * 60)


if __name__ == '__main__':
    run()
