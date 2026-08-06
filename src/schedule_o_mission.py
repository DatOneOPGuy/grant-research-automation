"""Recover mission text that filers wrote into Schedule O, not MissionDesc.

`recipient990_parser` reads Form 990 Part I `MissionDesc`. Thousands of filers
put a cross-reference there ("SEE SCHEDULE O") and the real mission narrative in
Schedule O, keyed by form-and-line reference. Schedule O is part of the e-filed
XML we already hold, so this is recovery from local data -- no fetching.

Matching is deliberately STRICT. A loose "mentions Part III" rule was tried
first and pulled in "NAME OF RELATED ORGANIZATION: ..." and "ALL OTHER PROGRAMS
69857. 0. 0." -- feeding that to the classifier as a mission would be worse than
the abstention it replaces. Only a reference that *is* the mission line counts:
Form 990 Part III Line 1 (statement of mission) or Part I Line 1 (briefly
describe the mission), with references naming another schedule excluded.

Writes data/grants_v2.db. Never touches data/grants.db.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from lxml import etree

DB = Path("data/grants_v2.db")
XML_DIR = Path("data/raw990")
EXTRACTOR_VERSION = "schedule-o-mission-1.0.0"
MIN_TEXT = 25
CHUNK = 500

# A pointer, not a mission: what the filer wrote in MissionDesc.
POINTER = re.compile(
    r"(SCHEDULE\s*O|SCH\s*O|SEE\s+PART|PART\s*III|SEE\s+STATEMENT|"
    r"SEE\s+ATTACH|SEE\s+PAGE|SEE\s+FORM\s*990)", re.I)
# References that belong to another schedule entirely.
OTHER_SCHEDULE = re.compile(r"\bSCHEDULE\s*[ABCDEFGHIJKLMNR]\b|\bSCH\s*[ABCDEFGHIJKLMNR]\b")
# The mission lines themselves, most specific first.
MISSION_REFS = (
    re.compile(r"^(?:FORM\s*990\s*)?PART\s*(?:III|3)\s*LINE\s*1\b"),
    re.compile(r"^(?:FORM\s*990\s*)?PART\s*(?:I|1)\s*LINE\s*1\b"),
    re.compile(r"^MISSION(?:\s*STATEMENT)?\b"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS r990_schedule_o_mission (
    object_id TEXT PRIMARY KEY,
    ein TEXT NOT NULL,
    tax_year INTEGER,
    mission_text TEXT NOT NULL,
    original_mission_text TEXT,
    source_reference TEXT NOT NULL,
    source_xpath TEXT NOT NULL,
    source_element TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    extracted_at_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_som_ein ON r990_schedule_o_mission(ein, tax_year);
"""


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def local(el) -> str:
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def normalize_ref(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", (value or "").upper()).strip()


def is_pointer(mission: str | None) -> bool:
    text = (mission or "").strip()
    if not text:
        return False
    return bool(POINTER.search(text)) or len(text) < MIN_TEXT


def extract(path: Path) -> tuple[str, str, str] | None:
    """Return (mission_text, matched_reference, xpath) or None."""
    try:
        root = etree.parse(str(path)).getroot()
    except (etree.XMLSyntaxError, OSError):
        return None
    pairs = []
    for el in root.iter():
        if local(el) != "FormAndLineReferenceDesc":
            continue
        parent = el.getparent()
        if parent is None:
            continue
        explanation = ""
        for child in parent:
            if local(child) == "ExplanationTxt":
                explanation = (child.text or "").strip()
        ref = normalize_ref(el.text)
        if OTHER_SCHEDULE.search(ref):
            continue
        pairs.append((ref, explanation, root.getroottree().getpath(parent)))
    for pattern in MISSION_REFS:
        for ref, explanation, xpath in pairs:
            if pattern.match(ref) and len(explanation) >= MIN_TEXT:
                return explanation, ref, xpath
    return None


def candidates(conn: sqlite3.Connection) -> list[tuple[str, str, int, str]]:
    rows = conn.execute(
        "SELECT object_id, ein, tax_year, mission_text FROM r990_documents "
        "WHERE parse_status='parsed'").fetchall()
    return [r for r in rows if is_pointer(r[3])]


def main() -> None:
    ap = argparse.ArgumentParser(prog="python3 -m src.schedule_o_mission",
                                 description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    started = time.monotonic()
    conn = sqlite3.connect(DB)
    if not args.dry_run:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM r990_schedule_o_mission")
        conn.commit()
    targets = candidates(conn)
    log(f"pointer-mission documents: {len(targets):,}")

    stamp = datetime.now(UTC).isoformat()
    batch, found, nofile, refs = [], 0, 0, {}
    for i, (object_id, ein, tax_year, original) in enumerate(targets, 1):
        path = XML_DIR / f"{object_id}_public.xml"
        if not path.exists():
            nofile += 1
            continue
        hit = extract(path)
        if hit is None:
            continue
        text, ref, xpath = hit
        found += 1
        refs[ref] = refs.get(ref, 0) + 1
        batch.append((object_id, ein, tax_year, text, original, ref, xpath,
                      "ExplanationTxt", EXTRACTOR_VERSION, stamp))
        if not args.dry_run and len(batch) >= CHUNK:
            conn.executemany(
                "INSERT OR REPLACE INTO r990_schedule_o_mission VALUES "
                "(?,?,?,?,?,?,?,?,?,?)", batch)
            conn.commit()
            batch.clear()
        if i % 2000 == 0:
            log(f"  scanned {i:,}/{len(targets):,} | recovered {found:,}")
    if not args.dry_run and batch:
        conn.executemany(
            "INSERT OR REPLACE INTO r990_schedule_o_mission VALUES "
            "(?,?,?,?,?,?,?,?,?,?)", batch)
        conn.commit()
    if not args.dry_run:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    pct = 100.0 * found / max(1, len(targets))
    log(f"recovered {found:,} of {len(targets):,} ({pct:.1f}%) "
        f"| missing xml: {nofile:,}")
    log("matched reference formats:")
    for ref, count in sorted(refs.items(), key=lambda kv: -kv[1])[:12]:
        log(f"    {count:>6}  {ref}")
    log(f"done in {time.monotonic() - started:,.0f}s"
        f"{' (dry run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
