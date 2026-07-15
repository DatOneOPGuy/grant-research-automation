"""Download, verify, and index all four official IRS EO BMF regions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sqlite3
from pathlib import Path

import requests
from tqdm import tqdm

from src.identity_normalize import normalize_identity_name, normalize_place

BMF_BASE = "https://www.irs.gov/pub/irs-soi"
REQUIRED_FILES = tuple(f"eo{i}.csv" for i in range(1, 5))
DEFAULT_DIR = Path("data/bmf")
DEFAULT_DB = Path("data/bmf_registry.db")
KEEP_COLUMNS = (
    "EIN",
    "NAME",
    "CITY",
    "STATE",
    "ZIP",
    "NTEE_CD",
    "FOUNDATION",
    "PF_FILING_REQ_CD",
    "TAX_PERIOD",
    "GROUP",
    "SUBSECTION",
    "AFFILIATION",
    "CLASSIFICATION",
    "RULING",
    "DEDUCTIBILITY",
    "ORGANIZATION",
    "STATUS",
    "ASSET_AMT",
    "INCOME_AMT",
    "REVENUE_AMT",
)

BMF_SCHEMA = """
CREATE TABLE IF NOT EXISTS bmf_organizations (
    ein TEXT PRIMARY KEY,
    organization_name TEXT NOT NULL,
    name_norm TEXT NOT NULL,
    city TEXT,
    city_norm TEXT,
    state TEXT,
    zip TEXT,
    ntee_code TEXT,
    foundation_code TEXT,
    pf_filing_req_code TEXT,
    tax_period TEXT,
    group_exemption_number TEXT,
    subsection_code TEXT,
    affiliation_code TEXT,
    classification_codes TEXT,
    ruling_date TEXT,
    deductibility_code TEXT,
    organization_code TEXT,
    status_code TEXT,
    asset_amount INTEGER,
    income_amount INTEGER,
    revenue_amount INTEGER,
    source_file TEXT NOT NULL,
    source_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bmf_sources (
    source_file TEXT PRIMARY KEY,
    source_sha256 TEXT NOT NULL,
    row_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bmf_name ON bmf_organizations(name_norm);
CREATE INDEX IF NOT EXISTS idx_bmf_name_state
    ON bmf_organizations(name_norm, state);
CREATE INDEX IF NOT EXISTS idx_bmf_name_state_city
    ON bmf_organizations(name_norm, state, city_norm);
CREATE INDEX IF NOT EXISTS idx_bmf_gen
    ON bmf_organizations(group_exemption_number);
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bmf-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_DB)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_missing(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "FoundationExplorer/1.0 (IRS public-data research)"
    for filename in REQUIRED_FILES:
        destination = directory / filename
        if destination.exists() and destination.stat().st_size > 0:
            continue
        temporary = destination.with_suffix(".csv.part")
        url = f"{BMF_BASE}/{filename}"
        with session.get(url, timeout=600, stream=True) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for block in response.iter_content(1024 * 1024):
                    if block:
                        handle.write(block)
        os.replace(temporary, destination)


def validate_sources(directory: Path) -> list[Path]:
    missing = [name for name in REQUIRED_FILES if not (directory / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Incomplete BMF: missing {', '.join(missing)}. Run with --download."
        )
    paths = [directory / name for name in REQUIRED_FILES]
    for path in paths:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            columns = set(next(csv.reader(handle)))
        absent = set(KEEP_COLUMNS) - columns
        if absent:
            raise ValueError(f"{path} is missing columns: {sorted(absent)}")
    return paths


def clean(value: str | None) -> str:
    return (value or "").strip()


def amount(row: dict[str, str], key: str) -> int | None:
    raw = clean(row.get(key))
    return int(raw) if raw.isdigit() else None


def organization_row(row: dict[str, str], source: str, digest: str) -> tuple:
    name = clean(row.get("NAME"))
    city = clean(row.get("CITY"))
    return (
        clean(row.get("EIN")).zfill(9),
        name,
        normalize_identity_name(name),
        city,
        normalize_place(city),
        clean(row.get("STATE")).upper(),
        clean(row.get("ZIP")),
        clean(row.get("NTEE_CD")),
        clean(row.get("FOUNDATION")),
        clean(row.get("PF_FILING_REQ_CD")),
        clean(row.get("TAX_PERIOD")),
        clean(row.get("GROUP")),
        clean(row.get("SUBSECTION")),
        clean(row.get("AFFILIATION")),
        clean(row.get("CLASSIFICATION")),
        clean(row.get("RULING")),
        clean(row.get("DEDUCTIBILITY")),
        clean(row.get("ORGANIZATION")),
        clean(row.get("STATUS")),
        amount(row, "ASSET_AMT"),
        amount(row, "INCOME_AMT"),
        amount(row, "REVENUE_AMT"),
        source,
        digest,
    )


def ingest_source(conn: sqlite3.Connection, path: Path) -> int:
    digest = sha256_file(path)
    count = 0
    batch = []
    sql = ("INSERT OR REPLACE INTO bmf_organizations VALUES "
           "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        for row in csv.DictReader(handle):
            candidate = organization_row(row, path.name, digest)
            if not candidate[0] or not candidate[1]:
                continue
            batch.append(candidate)
            count += 1
            if len(batch) == 10_000:
                conn.executemany(sql, batch)
                batch.clear()
        if batch:
            conn.executemany(sql, batch)
    conn.execute("INSERT OR REPLACE INTO bmf_sources VALUES (?,?,?)", (path.name, digest, count))
    conn.commit()
    return count


def build_registry(paths: list[Path], output: Path, rebuild: bool) -> None:
    if output.exists() and not rebuild:
        raise FileExistsError(f"Registry exists: {output}. Pass --rebuild to replace it.")
    if output.exists():
        output.unlink()
    conn = sqlite3.connect(output)
    conn.executescript(BMF_SCHEMA)
    try:
        for path in tqdm(paths, unit="region"):
            count = ingest_source(conn, path)
            print(f"{path.name}: {count:,} organizations")
        total = conn.execute("SELECT COUNT(*) FROM bmf_organizations").fetchone()[0]
        print(f"BMF registry: {total:,} unique EINs across all four regions")
    finally:
        conn.close()


def main() -> None:
    args = parse_args()
    if args.download:
        download_missing(args.bmf_dir)
    paths = validate_sources(args.bmf_dir)
    build_registry(paths, args.output, args.rebuild)


if __name__ == "__main__":
    main()
