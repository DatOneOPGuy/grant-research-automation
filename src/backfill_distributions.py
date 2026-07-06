"""Backfill the corrected `distributions` value into foundations.

Re-extracts only Part XII QualifyingDistributionsAmt (fallback Part I
ContriPaidRevAndExpnssAmt) per (EIN, tax year) and UPDATEs the row, fixing
the all-zero distributions bug without a full re-parse.
"""

import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from lxml import etree

from src.config import DB_PATH, RAW_DIR
from src.parser import _find_int, _find_text, detect_namespace


def extract_one(path_str: str):
    try:
        root = etree.parse(path_str).getroot()
    except Exception:
        return None
    ns = detect_namespace(root)
    if not ns:
        return None
    ein = (_find_text(root, './/irs:Filer/irs:EIN', ns)
           or _find_text(root, './/irs:EIN', ns))
    yr = (_find_text(root, './/irs:TaxYr', ns)
          or _find_text(root, './/irs:TaxYear', ns))
    if not ein or not yr.isdigit():
        return None
    dist = (_find_int(root, './/irs:QualifyingDistributionsAmt', ns)
            or _find_int(root, './/irs:ContriPaidRevAndExpnssAmt', ns))
    return ein, int(yr), dist


def run():
    files = [str(p) for p in Path(RAW_DIR).glob('*.xml')]
    print(f"Backfilling distributions from {len(files)} XMLs...",
          file=sys.stderr)
    conn = sqlite3.connect(DB_PATH)
    updated = 0
    with ProcessPoolExecutor() as ex:
        futures = [ex.submit(extract_one, f) for f in files]
        for i, fut in enumerate(as_completed(futures), 1):
            if i % 20000 == 0:
                print(f"  {i}/{len(files)}", file=sys.stderr)
                conn.commit()
            res = fut.result()
            if not res:
                continue
            ein, yr, dist = res
            cur = conn.execute(
                "UPDATE foundations SET distributions = ? "
                "WHERE ein = ? AND tax_year = ?", (dist, ein, yr),
            )
            updated += cur.rowcount
    conn.commit()
    stats = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN distributions > 0 THEN 1 ELSE 0 END), "
        "SUM(distributions) FROM foundations"
    ).fetchone()
    conn.close()
    print(f"Updated {updated} rows. Now {stats[1]} rows > 0, "
          f"total ${stats[2]:,}", file=sys.stderr)


if __name__ == '__main__':
    run()
