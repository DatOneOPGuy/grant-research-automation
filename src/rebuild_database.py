"""Build a provenance-preserving grants database from raw IRS XML files."""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
from collections.abc import Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

from tqdm import tqdm

from src.provenance_parser import parse_file
from src.provenance_schema import canonicalize_filings, create_schema
from src.rebuild_preflight import require_capacity

DEFAULT_OUTPUT = Path("data/grants_v2.db")
DEFAULT_INDEX = Path("data/pf_index_universe.csv")
DEFAULT_RAW = Path("data/raw")

FILING_COLUMNS = (
    "object_id",
    "source_path",
    "source_sha256",
    "return_id",
    "filing_type",
    "index_year",
    "index_tax_period",
    "index_return_type",
    "dln",
    "xml_batch_id",
    "ein",
    "return_type",
    "tax_year",
    "tax_period_end",
    "return_timestamp_raw",
    "return_timestamp_utc",
    "is_amended",
    "parser_version",
    "parse_status",
    "error_message",
    "parsed_at_utc",
)
FOUNDATION_COLUMNS = (
    "object_id",
    "ein",
    "tax_year",
    "organization_name",
    "city",
    "state",
    "country",
    "assets_eoy",
    "qualifying_distributions",
    "contributions_paid",
    "total_revenue",
    "website",
    "phone",
    "invite_only",
    "contact_person",
    "contact_address",
    "contact_phone",
    "contact_email",
    "application_format",
    "deadlines",
    "restrictions",
    "has_application_info",
)
GRANT_COLUMNS = (
    "grant_id",
    "object_id",
    "ein",
    "tax_year",
    "schedule_type",
    "source_xpath",
    "row_ordinal",
    "recipient_name",
    "recipient_ein_raw",
    "recipient_city",
    "recipient_state",
    "recipient_country",
    "recipient_foundation_status",
    "is_foreign",
    "amount_text",
    "signed_amount",
    "amount_status",
    "purpose",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bmf-dir", type=Path, default=Path("data/bmf"))
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def clean_metadata(row: dict[str, str]) -> dict[str, str | int | None]:
    cleaned: dict[str, str | int | None] = {}
    for key, value in row.items():
        value = (value or "").strip()
        cleaned[key] = value or None
    if cleaned.get("index_year"):
        cleaned["index_year"] = int(str(cleaned["index_year"]))
    if cleaned.get("EIN"):
        cleaned["EIN"] = str(cleaned["EIN"]).zfill(9)
    return cleaned


def load_index(path: Path) -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {
            str(row["OBJECT_ID"]).strip(): clean_metadata(row)
            for row in csv.DictReader(handle)
            if str(row.get("OBJECT_ID") or "").strip()
        }


def object_id(path: Path) -> str:
    return path.stem.removesuffix("_public")


def insert_sql(table: str, columns: tuple[str, ...]) -> str:
    placeholders = ",".join("?" for _ in columns)
    return f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"


def values(record: dict, columns: tuple[str, ...]) -> tuple:
    return tuple(record.get(column) for column in columns)


def insert_result(conn: sqlite3.Connection, result: dict) -> None:
    conn.execute(insert_sql("filings", FILING_COLUMNS), values(result["filing"], FILING_COLUMNS))
    if result["foundation"]:
        conn.execute(
            insert_sql("foundation_filings", FOUNDATION_COLUMNS),
            values(result["foundation"], FOUNDATION_COLUMNS),
        )
    if result["grants"]:
        conn.executemany(
            insert_sql("grant_transactions", GRANT_COLUMNS),
            (values(grant, GRANT_COLUMNS) for grant in result["grants"]),
        )


def completed_ids(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT object_id FROM filings")}


def bounded_parallel(work: Iterable[tuple[str, dict]], workers: int) -> Iterator[dict]:
    """Keep only a small number of XML parse results resident in memory."""
    iterator = iter(work)
    try:
        pool = ProcessPoolExecutor(max_workers=workers)
    except (PermissionError, NotImplementedError):
        print("Process workers unavailable; falling back to sequential parsing.")
        for path, metadata in iterator:
            yield parse_file(path, metadata)
        return
    with pool:
        pending = set()
        for _ in range(workers * 3):
            try:
                path, metadata = next(iterator)
            except StopIteration:
                break
            pending.add(pool.submit(parse_file, path, metadata))
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                yield future.result()
                try:
                    path, metadata = next(iterator)
                except StopIteration:
                    continue
                pending.add(pool.submit(parse_file, path, metadata))


def result_stream(work: list[tuple[str, dict]], workers: int) -> Iterable[dict]:
    if workers == 1:
        return (parse_file(path, metadata) for path, metadata in work)
    return bounded_parallel(work, workers)


def prepare_output(path: Path, resume: bool) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not resume:
        raise FileExistsError(f"Output already exists: {path}. Use --resume or a new path.")
    conn = sqlite3.connect(path)
    create_schema(conn)
    return conn


def select_work(
    raw_dir: Path, metadata: dict[str, dict], done: set[str], limit: int | None
) -> list[tuple[str, dict]]:
    paths = sorted(raw_dir.glob("*.xml"))
    work = [
        (str(path), metadata.get(object_id(path), {}))
        for path in paths
        if object_id(path) not in done
    ]
    return work[:limit] if limit is not None else work


def ingest(conn: sqlite3.Connection, work: list[tuple[str, dict]], workers: int) -> None:
    conn.execute("BEGIN")
    try:
        for index, result in enumerate(
            tqdm(result_stream(work, workers), total=len(work), unit="filing"), 1
        ):
            insert_result(conn, result)
            if index % 250 == 0:
                conn.commit()
                conn.execute("BEGIN")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def print_summary(conn: sqlite3.Connection, canonical_count: int) -> None:
    counts = conn.execute(
        "SELECT parse_status, COUNT(*) FROM filings GROUP BY parse_status ORDER BY 1"
    ).fetchall()
    grants = conn.execute(
        "SELECT schedule_type, amount_status, COUNT(*), COALESCE(SUM(signed_amount),0) "
        "FROM canonical_grants GROUP BY schedule_type, amount_status ORDER BY 1,2"
    ).fetchall()
    print(f"Canonical foundation-years: {canonical_count:,}")
    for status, count in counts:
        print(f"  filings.{status}: {count:,}")
    for schedule, status, count, amount in grants:
        print(f"  grants.{schedule}.{status}: {count:,} rows / ${amount:,.0f}")


def main() -> None:
    args = parse_args()
    if args.limit is None:
        require_capacity(args.raw_dir, args.output, args.bmf_dir)
    if args.preflight_only:
        return
    metadata = load_index(args.index)
    conn = prepare_output(args.output, args.resume)
    try:
        work = select_work(args.raw_dir, metadata, completed_ids(conn), args.limit)
        print(f"Parsing {len(work):,} filings with {args.workers} worker(s) into {args.output}")
        ingest(conn, work, args.workers)
        canonical_count = canonicalize_filings(conn)
        print_summary(conn, canonical_count)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
