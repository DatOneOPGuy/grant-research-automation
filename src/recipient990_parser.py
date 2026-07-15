"""Parse recipient 990/990-EZ XMLs into documentary evidence rows.

Extraction only — mission statements and program-service descriptions are
stored verbatim with full provenance (object ID, source SHA-256, tax year,
amendment flag, parser version). No classification happens here; the text is
the input to a later, separate classification build.

Canonical policy matches the 990-PF pipeline: one filing per EIN/tax-year by
return timestamp, then amendment flag, then object ID.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from json import dumps
from pathlib import Path

from lxml import etree

from src.provenance_xml import (
    descendant_text,
    first_descendant,
    local_name,
    normalize_timestamp,
)

PARSER_VERSION = "r990-1.0.0"
ACCEPTED_TYPES = {"990", "990EZ"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS r990_documents (
    object_id TEXT PRIMARY KEY,
    ein TEXT NOT NULL,
    return_type TEXT,
    tax_year INTEGER,
    return_timestamp_utc TEXT,
    is_amended INTEGER NOT NULL DEFAULT 0,
    org_name TEXT,
    city TEXT,
    state TEXT,
    website TEXT,
    mission_text TEXT,
    program_texts_json TEXT,
    source_sha256 TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    parse_status TEXT NOT NULL,
    error_message TEXT,
    parsed_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_r990_ein ON r990_documents(ein, tax_year);
"""


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def program_texts(root: etree._Element) -> list[str]:
    """Every Desc under a ProgSrvcAccom* group, in document order."""
    texts: list[str] = []
    for element in root.iter():
        if not local_name(element).startswith("ProgSrvcAccom"):
            continue
        for child in element.iter():
            if local_name(child) in ("Desc", "DescriptionProgramSrvcAccomTxt") \
                    and child.text and child.text.strip():
                texts.append(child.text.strip())
    seen: set[str] = set()
    unique = []
    for text in texts:
        if text not in seen:
            seen.add(text)
            unique.append(text)
    return unique


def parse_one(path_text: str) -> dict:
    path = Path(path_text)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    object_id = path.stem.removesuffix("_public")
    base = {
        "object_id": object_id, "source_sha256": digest,
        "parser_version": PARSER_VERSION,
    }
    try:
        root = etree.fromstring(payload, parser=etree.XMLParser(
            resolve_entities=False, no_network=True, huge_tree=True))
    except etree.XMLSyntaxError as error:
        return {**base, "ein": "", "parse_status": "parse_error",
                "error_message": str(error)[:300]}
    return_type = descendant_text(root, "ReturnTypeCd")
    if return_type not in ACCEPTED_TYPES:
        return {**base, "ein": descendant_text(root, "EIN"),
                "return_type": return_type,
                "parse_status": "excluded_return_type", "error_message": None}
    filer = first_descendant(root, "Filer")
    tax_year_raw = descendant_text(root, "TaxYr", "TaxYear")
    mission = descendant_text(
        root, "ActivityOrMissionDesc", "MissionDesc", "PrimaryExemptPurposeTxt")
    return {
        **base,
        "ein": descendant_text(filer, "EIN"),
        "return_type": return_type,
        "tax_year": int(tax_year_raw) if tax_year_raw.isdigit() else None,
        "return_timestamp_utc": normalize_timestamp(descendant_text(root, "ReturnTs")),
        "is_amended": int(descendant_text(root, "AmendedReturnInd").upper() == "X"),
        "org_name": descendant_text(
            filer, "BusinessNameLine1Txt", "BusinessNameLine1"),
        "city": descendant_text(filer, "CityNm", "City"),
        "state": descendant_text(filer, "StateAbbreviationCd", "State"),
        "website": descendant_text(root, "WebsiteAddressTxt", "WebSiteAddressTxt"),
        "mission_text": mission,
        "program_texts_json": dumps(program_texts(root)),
        "parse_status": "parsed",
        "error_message": None,
    }


COLUMNS = ("object_id", "ein", "return_type", "tax_year",
           "return_timestamp_utc", "is_amended", "org_name", "city", "state",
           "website", "mission_text", "program_texts_json", "source_sha256",
           "parser_version", "parse_status", "error_message")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants_v2.db"))
    parser.add_argument("--xml-dir", type=Path, default=Path("data/raw990"))
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    conn = sqlite3.connect(f"file:{args.db.resolve()}?mode=rw", uri=True, timeout=60)
    conn.executescript(SCHEMA)
    done = {row[0] for row in conn.execute("SELECT object_id FROM r990_documents")}
    work = [str(p) for p in sorted(args.xml_dir.glob("*.xml"))
            if p.stem.removesuffix("_public") not in done]
    log(f"parsing {len(work):,} filings ({len(done):,} already done)")
    insert = (f"INSERT OR IGNORE INTO r990_documents ({','.join(COLUMNS)}) "
              f"VALUES ({','.join('?' for _ in COLUMNS)})")
    started = time.monotonic()
    processed = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        batch = []
        for record in pool.map(parse_one, work, chunksize=200):
            batch.append(tuple(record.get(col) for col in COLUMNS))
            if len(batch) >= 2_000:
                conn.executemany(insert, batch)
                conn.commit()
                processed += len(batch)
                batch.clear()
                rate = processed / max(time.monotonic() - started, 1e-9)
                log(f"  {processed:,}/{len(work):,} parsed | {rate:,.0f}/s")
        if batch:
            conn.executemany(insert, batch)
            conn.commit()
            processed += len(batch)
    for status, count in conn.execute(
        "SELECT parse_status, COUNT(*) FROM r990_documents GROUP BY 1"):
        log(f"  {status}: {count:,}")
    conn.close()


if __name__ == "__main__":
    main()
