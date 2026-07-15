"""Stream IRS TEOS zips and extract only recipient-990 target filings.

Reads r990_fetch_list (built by recipient990_targets), streams each monthly
zip once, extracts only matching OBJECT_IDs into data/raw990/, and records
per-zip completion so a multi-day run resumes at the first unfinished zip.
Polite: sequential downloads, one zip at a time, pause between zips.
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import requests

from src.downloader import discover_irs_zip_urls

YEARS = (2023, 2024, 2025)
PAUSE_SECONDS = 5
SCHEMA = """
CREATE TABLE IF NOT EXISTS r990_zip_progress (
    zip_url TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('done','failed')),
    extracted INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    finished_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
"""


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def target_objects(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute(
        "SELECT object_id FROM r990_fetch_list WHERE fetched=0")}


def mark_extracted(conn: sqlite3.Connection, targets: set[str], stem: str) -> None:
    conn.execute(
        "UPDATE r990_fetch_list SET fetched=1 WHERE object_id=?", (stem,))
    targets.discard(stem)


def extract_with_tool(spool: Path, targets: set[str], out_dir: Path,
                      conn: sqlite3.Connection) -> int:
    """Shell-tool fallback for zips Python's zipfile rejects.

    bsdtar handles deflate64; Info-ZIP unzip salvages archives with damaged
    central directories (several IRS 2025 zips carry 76 stray bytes and a
    broken trailer — unzip extracts every intact member and errors only at
    the end, so its exit status is deliberately not checked).
    """
    extracted = 0
    with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
        result = subprocess.run(["bsdtar", "-xf", str(spool), "-C", tmp],
                                check=False, capture_output=True)
        if result.returncode != 0:
            log("  bsdtar failed; salvaging with unzip (best effort)")
            subprocess.run(["unzip", "-oq", str(spool), "-d", tmp],
                           check=False, capture_output=True)
        for path in Path(tmp).rglob("*.xml"):
            stem = path.stem.removesuffix("_public")
            if stem not in targets:
                continue
            destination = out_dir / f"{stem}_public.xml"
            if not destination.exists():
                path.rename(destination)
            mark_extracted(conn, targets, stem)
            extracted += 1
    return extracted


def extract_zip(session: requests.Session, url: str, targets: set[str],
                out_dir: Path, conn: sqlite3.Connection) -> tuple[int, str | None]:
    name = url.rsplit("/", 1)[-1]
    log(f"streaming {name} ({len(targets):,} objects still wanted)")
    spool = out_dir / f".{name}.part"
    try:
        with session.get(url, timeout=1800, stream=True) as resp:
            resp.raise_for_status()
            fetched_mb = 0
            with spool.open("wb") as handle:
                for block in resp.iter_content(1 << 22):
                    handle.write(block)
                    fetched_mb += len(block) / 1e6
        log(f"  downloaded {fetched_mb:,.0f}MB; scanning members")
        extracted = 0
        try:
            with zipfile.ZipFile(spool) as archive:
                for member in archive.namelist():
                    stem = Path(member).stem.removesuffix("_public")
                    if stem not in targets:
                        continue
                    destination = out_dir / f"{stem}_public.xml"
                    if not destination.exists():
                        destination.write_bytes(archive.read(member))
                    mark_extracted(conn, targets, stem)
                    extracted += 1
        except NotImplementedError:
            log("  unsupported compression; falling back to bsdtar full extract")
            extracted = extract_with_tool(spool, targets, out_dir, conn)
        conn.commit()
        return extracted, None
    except (requests.RequestException, zipfile.BadZipFile, OSError,
            subprocess.CalledProcessError) as error:
        return 0, f"{type(error).__name__}: {str(error)[:200]}"
    finally:
        spool.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants_v2.db"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/raw990"))
    parser.add_argument("--limit-zips", type=int, default=None)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{args.db.resolve()}?mode=rw", uri=True, timeout=60)
    conn.executescript(SCHEMA)
    session = requests.Session()
    session.headers["User-Agent"] = "FoundationExplorer/1.0 (IRS public-data research)"
    done = {row[0] for row in conn.execute(
        "SELECT zip_url FROM r990_zip_progress WHERE status='done'")}
    urls = [url for year in YEARS for url in discover_irs_zip_urls(year)
            if url not in done]
    if args.limit_zips:
        urls = urls[:args.limit_zips]
    targets = target_objects(conn)
    log(f"{len(urls)} zips to process, {len(done)} already done, "
        f"{len(targets):,} objects wanted")
    for i, url in enumerate(urls, 1):
        if not targets:
            log("all targets extracted; stopping early")
            break
        extracted, error = extract_zip(session, url, targets, args.out_dir, conn)
        if error:
            log(f"  FAILED {url}: {error}")
            conn.execute(
                "INSERT OR REPLACE INTO r990_zip_progress "
                "(zip_url, status, extracted, error) VALUES (?,?,?,?)",
                (url, "failed", 0, error))
        else:
            log(f"  extracted {extracted:,} | zip {i}/{len(urls)} | "
                f"{len(targets):,} still wanted")
            conn.execute(
                "INSERT OR REPLACE INTO r990_zip_progress "
                "(zip_url, status, extracted, error) VALUES (?,?,?,NULL)",
                (url, "done", extracted))
        conn.commit()
        time.sleep(PAUSE_SECONDS)
    remaining = len(target_objects(conn))
    log(f"fetch pass complete; {remaining:,} objects still unfetched")


if __name__ == "__main__":
    main()
