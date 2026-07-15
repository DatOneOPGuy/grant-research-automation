"""Phase A of recipient identity: chunked, checkpointed normalization scan.

Reads canonical paid grants in rowid order, normalizes recipient name/city in
Python (memoized — no SQLite UDF callbacks), and persists one `grant_norm` row
per grant. Progress is committed with a checkpoint every chunk, so a killed
run resumes from the last committed rowid and loses at most one chunk.
"""

from __future__ import annotations

import sqlite3
import sys
import time
from functools import lru_cache

from src.identity_normalize import mention_id, normalize_identity_name, normalize_place

CHUNK_ROWS = 200_000

GRANT_NORM_SCHEMA = """
CREATE TABLE IF NOT EXISTS grant_norm (
    run_id TEXT NOT NULL,
    grant_id TEXT NOT NULL,
    mention_id TEXT NOT NULL,
    name_norm TEXT NOT NULL,
    display_name TEXT,
    city_norm TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    raw_recipient_ein TEXT,
    signed_amount INTEGER NOT NULL,
    tax_year INTEGER,
    PRIMARY KEY (run_id, grant_id)
);
CREATE TABLE IF NOT EXISTS identity_progress (
    run_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    last_rowid INTEGER NOT NULL,
    rows_done INTEGER NOT NULL,
    updated_at_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, phase)
);
CREATE INDEX IF NOT EXISTS idx_grant_norm_mention
    ON grant_norm(run_id, mention_id);
"""

_norm_name = lru_cache(maxsize=500_000)(normalize_identity_name)
_norm_place = lru_cache(maxsize=100_000)(normalize_place)


def clean_ein(value: str | None) -> str:
    """Digits-only EIN, zero-filled to the BMF's 9-char format; '' if unusable."""
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    return digits.zfill(9) if 1 <= len(digits) <= 9 else ""


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _checkpoint(conn: sqlite3.Connection, run_id: str, phase: str,
                last_rowid: int, rows_done: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO identity_progress "
        "VALUES (?,?,?,?,strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
        (run_id, phase, last_rowid, rows_done),
    )


def resume_point(conn: sqlite3.Connection, run_id: str, phase: str) -> tuple[int, int]:
    row = conn.execute(
        "SELECT last_rowid, rows_done FROM identity_progress "
        "WHERE run_id=? AND phase=?",
        (run_id, phase),
    ).fetchone()
    return (row[0], row[1]) if row else (0, 0)


def load_canonical_objects(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT object_id FROM canonical_filings")}


def scan_paid_grants(conn: sqlite3.Connection, run_id: str) -> int:
    """Chunked normalization scan. Resumable; returns rows written."""
    canonical = load_canonical_objects(conn)
    _log(f"[mentions] canonical filings loaded: {len(canonical):,}")
    last_rowid, rows_done = resume_point(conn, run_id, "grant_norm")
    if last_rowid:
        _log(f"[mentions] resuming after rowid {last_rowid:,} ({rows_done:,} rows done)")
    started = time.monotonic()
    while True:
        rows = conn.execute(
            """
            SELECT rowid, grant_id, object_id, recipient_name, recipient_city,
                   recipient_state, recipient_country, recipient_ein_raw,
                   signed_amount, tax_year
            FROM grant_transactions
            WHERE rowid > ? AND schedule_type='paid' AND amount_status='positive'
            ORDER BY rowid LIMIT ?
            """,
            (last_rowid, CHUNK_ROWS),
        ).fetchall()
        if not rows:
            break
        batch = []
        for (rid, grant_id, object_id, name, city, state, country, raw_ein,
             amount, tax_year) in rows:
            last_rowid = rid
            if object_id not in canonical or not (name or "").strip():
                continue
            name_norm = _norm_name(name)
            if not name_norm:
                continue
            city_norm = _norm_place(city)
            state_up = (state or "").upper()
            country_up = (country or "").upper()
            batch.append((
                run_id, grant_id,
                mention_id(name_norm, city_norm, state_up, country_up),
                name_norm, name, city_norm, city, state_up, country_up,
                clean_ein(raw_ein), amount, tax_year,
            ))
        conn.executemany(
            "INSERT OR IGNORE INTO grant_norm VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            batch,
        )
        rows_done += len(batch)
        _checkpoint(conn, run_id, "grant_norm", last_rowid, rows_done)
        conn.commit()
        rate = rows_done / max(time.monotonic() - started, 1e-9)
        _log(f"[mentions] rowid {last_rowid:,} | {rows_done:,} rows | {rate:,.0f} rows/s")
    _log(f"[mentions] scan complete: {rows_done:,} normalized grant rows")
    return rows_done
