"""Backfill Phase 2 profile fields into foundations from raw XMLs.

Re-extracts only the new fields (website, phone, revenue, invite-only,
2a-2d block) per (EIN, tax year) and UPDATEs the existing rows, so a full
re-parse is not needed.
"""

import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from lxml import etree

from src.config import DB_PATH, RAW_DIR
from src.parser import detect_namespace, migrate_schema, _find_text
from src.profile_fields import extract_profile_fields, PROFILE_COLUMNS


def extract_one(path_str: str):
    """Return (ein, tax_year, fields) or None."""
    try:
        root = etree.parse(path_str).getroot()
    except Exception:
        return None
    ns = detect_namespace(root)
    if not ns:
        return None
    ein = (
        _find_text(root, './/irs:Filer/irs:EIN', ns)
        or _find_text(root, './/irs:EIN', ns)
    )
    if not ein:
        return None
    tax_year = (
        _find_text(root, './/irs:TaxYr', ns)
        or _find_text(root, './/irs:TaxYear', ns)
    )
    if not tax_year.isdigit():
        return None
    return ein, int(tax_year), extract_profile_fields(root, ns)


def run():
    files = [str(p) for p in Path(RAW_DIR).glob('*.xml')]
    print(f"Backfilling profile fields from {len(files)} XMLs...",
          file=sys.stderr)

    conn = sqlite3.connect(DB_PATH)
    migrate_schema(conn)
    set_clause = ', '.join(f"{c} = ?" for c in PROFILE_COLUMNS)
    sql = (f"UPDATE foundations SET {set_clause} "
           f"WHERE ein = ? AND tax_year = ?")

    updated = skipped = 0
    with ProcessPoolExecutor() as ex:
        futures = [ex.submit(extract_one, f) for f in files]
        for i, fut in enumerate(as_completed(futures), 1):
            if i % 4000 == 0:
                print(f"  {i}/{len(files)}", file=sys.stderr)
                conn.commit()
            res = fut.result()
            if not res:
                skipped += 1
                continue
            ein, tax_year, fields = res
            cur = conn.execute(
                sql, [fields[c] for c in PROFILE_COLUMNS] + [ein, tax_year]
            )
            if cur.rowcount:
                updated += 1
            else:
                skipped += 1

    conn.commit()
    filled = conn.execute(
        "SELECT COUNT(*), SUM(website != ''), SUM(phone != ''), "
        "SUM(revenue IS NOT NULL), SUM(invite_only = 1), "
        "SUM(has_application_info = 1) FROM foundations"
    ).fetchone()
    conn.close()

    print(f"Updated {updated} rows, skipped {skipped}", file=sys.stderr)
    print(f"foundations rows={filled[0]}: website={filled[1]}, "
          f"phone={filled[2]}, revenue={filled[3]}, "
          f"invite_only={filled[4]}, application_info={filled[5]}",
          file=sys.stderr)


if __name__ == '__main__':
    run()
