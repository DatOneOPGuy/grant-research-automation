"""Extract and parse 990-PF application submission deadlines.

There is no date on an individual grant -- the 990-PF grant schedule lists what
was paid during the tax year and nothing more -- so a foundation's *giving*
cannot be placed in a season. What CAN be placed in a season is when it accepts
applications, which is the thing a fundraiser actually needs to plan around.

Form 990-PF Part XV line 2b carries `SubmissionDeadlinesTxt`, free text the
filer writes themselves. It ranges from "APRIL 1" to "First Friday in May" to
"Submissions are year round" to "SEE FOOTNOTES". This module reads it from the
canonical filing already on disk and normalises it into:

  kind    -- dated | rolling | none | unparseable
  months  -- the months named, as a sorted list of 1-12

Deliberately conservative. A deadline that cannot be confidently placed in a
month is recorded as unparseable rather than guessed, because a fundraiser
planning outreach around a wrong month is worse served than one told we do not
know.

Writes data/grants_v2.db. Never touches data/grants.db.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

from lxml import etree

DB = Path("data/grants_v2.db")
CHUNK = 5_000

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
MONTH_RX = re.compile(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b", re.I)
# Numeric dates: 4/1, 04-01, 4/1/2025. Month is the leading component.
NUMERIC_RX = re.compile(r"\b(1[0-2]|0?[1-9])\s*[/-]\s*(3[01]|[12]\d|0?[1-9])\b")
QUARTER_RX = re.compile(r"\b(?:q(?:uarter)?\s*([1-4])|([1-4])(?:st|nd|rd|th)\s+quarter)\b", re.I)
QUARTER_MONTHS = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12]}

NONE_RX = re.compile(
    r"^\W*(none|n/?a|no|nil|not applicable|no deadlines?|"
    r"there are no submission deadlines?|no submission deadlines?)\W*$", re.I)
ROLLING_RX = re.compile(
    r"\b(year[\s-]?round|any\s?time|anytime|rolling|ongoing|continuous|"
    r"as (?:they are )?received|throughout the year|no deadline|"
    r"accepted at any time|open all year|monthly|quarterly basis)\b", re.I)
# Cross-references we cannot resolve -- the detail is in an attachment.
REFERENCE_RX = re.compile(
    r"\b(see\s+(footnote|attach|statement|schedule|part|below)|attached)\b",
    re.I)

SCHEMA = """
CREATE TABLE IF NOT EXISTS foundation_deadlines (
    ein TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    tax_year INTEGER,
    raw_text TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('dated','rolling','none','unparseable')),
    months_json TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    extracted_at_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deadlines_kind ON foundation_deadlines(kind);
"""
VERSION = "deadlines-1.0.0"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def parse_deadline(text: str) -> tuple[str, list[int]]:
    """(kind, months). Conservative: guessing a month is worse than admitting
    we cannot read it."""
    raw = (text or "").strip()
    if not raw or NONE_RX.match(raw):
        return "none", []
    months: set[int] = set()
    for match in MONTH_RX.finditer(raw):
        months.add(MONTHS[match.group(1).lower()])
    for match in NUMERIC_RX.finditer(raw):
        months.add(int(match.group(1)))
    for match in QUARTER_RX.finditer(raw):
        quarter = int(match.group(1) or match.group(2))
        months.update(QUARTER_MONTHS[quarter])
    if months:
        # "no deadline, apply any time in January" is still rolling in spirit,
        # but a named month is actionable, so dated wins when both appear.
        return "dated", sorted(months)
    if ROLLING_RX.search(raw):
        return "rolling", []
    if REFERENCE_RX.search(raw):
        return "unparseable", []
    return "unparseable", []


def local_name(element) -> str:
    return etree.QName(element).localname if isinstance(element.tag, str) else ""


def read_deadline(path: str) -> str | None:
    try:
        root = etree.parse(path).getroot()
    except (etree.XMLSyntaxError, OSError):
        return None
    for element in root.iter():
        if local_name(element) == "SubmissionDeadlinesTxt":
            text = (element.text or "").strip()
            if text:
                return text
    return None


def main() -> None:
    ap = argparse.ArgumentParser(prog="python3 -m src.application_deadlines",
                                 description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    started = time.monotonic()
    conn = sqlite3.connect(DB, timeout=60)
    if not args.dry_run:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM foundation_deadlines")
        conn.commit()
    rows = conn.execute("""
        SELECT cf.ein, cf.object_id, cf.tax_year, f.source_path
        FROM canonical_filings cf JOIN filings f ON f.object_id = cf.object_id
        WHERE cf.tax_year = (SELECT MAX(tax_year) FROM canonical_filings c2
                             WHERE c2.ein = cf.ein)""").fetchall()
    log(f"canonical filings: {len(rows):,}")

    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    batch, found, counts = [], 0, {"dated": 0, "rolling": 0, "none": 0,
                                   "unparseable": 0}
    for index, (ein, object_id, tax_year, path) in enumerate(rows, 1):
        if not path or not os.path.exists(path):
            continue
        text = read_deadline(path)
        if text is None:
            continue
        found += 1
        kind, months = parse_deadline(text)
        counts[kind] += 1
        batch.append((ein, object_id, tax_year, text[:400], kind,
                      json.dumps(months), VERSION, stamp))
        if not args.dry_run and len(batch) >= CHUNK:
            conn.executemany("INSERT OR REPLACE INTO foundation_deadlines "
                             "VALUES (?,?,?,?,?,?,?,?)", batch)
            conn.commit()
            batch.clear()
        if index % 25_000 == 0:
            log(f"  scanned {index:,}/{len(rows):,} | with a deadline {found:,}")
    if not args.dry_run and batch:
        conn.executemany("INSERT OR REPLACE INTO foundation_deadlines "
                         "VALUES (?,?,?,?,?,?,?,?)", batch)
        conn.commit()
    if not args.dry_run:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    log(f"filings carrying SubmissionDeadlinesTxt: {found:,} "
        f"({100 * found / max(1, len(rows)):.1f}%)")
    for kind, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        log(f"  {kind:<13}{count:>7,}")
    log(f"done in {time.monotonic() - started:,.0f}s"
        f"{' (dry run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
