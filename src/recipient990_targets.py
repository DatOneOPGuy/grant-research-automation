"""Build the recipient-990 fetch list: Lists A/B/C, deduped, index-matched.

List A: resolved entities with TY2023-24 paid dollars >= $100k (fetch by EIN).
List B: PC-status unresolved mentions >= $100k — matched against the e-file
        index by unique normalized taxpayer name (same strictness bar as BMF
        matching; the fetched filing's own address must later confirm
        geography before any identity is asserted).
List C: foundation-code-10 houses of worship, tradition-pending (by EIN;
        expected low yield — churches are exempt from filing).

Writes r990_targets and r990_fetch_list into grants_v2.db. Read-only against
identity tables; no downloads happen here.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from src.identity_normalize import normalize_identity_name

THRESHOLD = 100_000
RETURN_TYPES = {"990", "990EZ"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS r990_targets (
    identity_run_id TEXT NOT NULL,
    target_list TEXT NOT NULL CHECK (target_list IN ('A','B','C')),
    target_key TEXT NOT NULL,          -- entity_id (A/C) or mention_id (B)
    ein TEXT,                          -- known EIN (A/C); NULL for B until index match
    name_norm TEXT,
    paid_2324 INTEGER NOT NULL DEFAULT 0,
    match_status TEXT NOT NULL,        -- 'ein_known' | 'index_unique_name' |
                                       -- 'index_ambiguous' | 'index_no_match'
    matched_ein TEXT,
    PRIMARY KEY (identity_run_id, target_list, target_key)
);
CREATE TABLE IF NOT EXISTS r990_fetch_list (
    identity_run_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    ein TEXT NOT NULL,
    return_type TEXT NOT NULL,
    tax_period TEXT,
    index_year INTEGER,
    taxpayer_name TEXT,
    fetched INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (identity_run_id, object_id)
);
"""


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def latest_run(conn: sqlite3.Connection) -> str:
    return conn.execute(
        "SELECT run_id FROM identity_runs ORDER BY created_at_utc DESC LIMIT 1"
    ).fetchone()[0]


def entity_dollars(conn: sqlite3.Connection, run_id: str) -> dict[str, int]:
    return dict(conn.execute("""
        SELECT e.entity_id,
               SUM(CASE WHEN g.tax_year IN (2023,2024) THEN g.signed_amount
                        ELSE 0 END)
        FROM grant_norm g
        JOIN recipient_entity_mentions em
          ON em.run_id=g.run_id AND em.mention_id=g.mention_id
        JOIN recipient_entities e
          ON e.run_id=em.run_id AND e.entity_id=em.entity_id
        WHERE g.run_id=? GROUP BY 1
    """, (run_id,)).fetchall())


def build_lists(conn: sqlite3.Connection, run_id: str) -> None:
    dollars = entity_dollars(conn, run_id)
    log(f"[targets] entity dollars computed: {len(dollars):,}")
    rows: list[tuple] = []
    for entity_id, ein in conn.execute(
        "SELECT entity_id, bmf_ein FROM recipient_entities "
        "WHERE run_id=? AND identity_status='matched_bmf'", (run_id,)):
        paid = dollars.get(entity_id, 0)
        if paid >= THRESHOLD:
            rows.append((run_id, "A", entity_id, ein, None, paid, "ein_known", ein))
    # List C: code-10 pending — matched entities whose classification release
    # has no resolution and whose BMF row is foundation code 10.
    for entity_id, ein in conn.execute("""
        SELECT e.entity_id, e.bmf_ein
        FROM recipient_entities e
        JOIN bmf.bmf_organizations b ON b.ein=e.bmf_ein
        WHERE e.run_id=? AND b.foundation_code='10'
          AND e.entity_id NOT IN (
            SELECT entity_id FROM classification_resolutions r
            JOIN classification_releases rel ON rel.release_id=r.release_id
            WHERE rel.identity_run_id=?)
    """, (run_id, run_id)):
        rows.append((run_id, "C", entity_id, ein, None,
                     dollars.get(entity_id, 0), "ein_known", ein))
    for mention_id, name_norm, paid in conn.execute("""
        SELECT m.mention_id, m.name_norm,
               SUM(CASE WHEN g.tax_year IN (2023,2024) THEN g.signed_amount
                        ELSE 0 END) AS paid
        FROM recipient_mentions m
        JOIN recipient_entity_mentions em
          ON em.run_id=m.run_id AND em.mention_id=m.mention_id
        JOIN recipient_entities e
          ON e.run_id=em.run_id AND e.entity_id=em.entity_id
        JOIN grant_norm g ON g.run_id=m.run_id AND g.mention_id=m.mention_id
        WHERE m.run_id=? AND e.identity_status='unresolved'
          AND m.status_bucket='PC'
        GROUP BY 1 HAVING paid >= ?
    """, (run_id, THRESHOLD)):
        rows.append((run_id, "B", mention_id, None, name_norm, paid, "pending", None))
    conn.executemany(
        "INSERT OR REPLACE INTO r990_targets VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    for lst, n in conn.execute(
        "SELECT target_list, COUNT(*) FROM r990_targets WHERE identity_run_id=? "
        "GROUP BY 1", (run_id,)):
        log(f"[targets] list {lst}: {n:,} targets")


def load_index(index_dir: Path) -> tuple[dict[str, list], dict[str, set[str]]]:
    """Return (ein -> filings rows, name_norm -> set of EINs) for 990/990EZ."""
    by_ein: dict[str, list] = defaultdict(list)
    by_name: dict[str, set[str]] = defaultdict(set)
    files = sorted(index_dir.glob("*.csv"))
    if not files:
        raise SystemExit(f"No index CSVs in {index_dir}")
    for path in files:
        year = int(path.name[:4])
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
            for row in csv.DictReader(fh):
                rt = (row.get("RETURN_TYPE") or "").strip().upper()
                if rt not in RETURN_TYPES:
                    continue
                ein = (row.get("EIN") or "").strip().zfill(9)
                record = (
                    str(row.get("OBJECT_ID") or "").strip(), ein, rt,
                    (row.get("TAX_PERIOD") or "").strip(), year,
                    (row.get("TAXPAYER_NAME") or "").strip(),
                )
                if record[0]:
                    by_ein[ein].append(record)
                    name = normalize_identity_name(record[5])
                    if name:
                        by_name[name].add(ein)
        log(f"[index] {path.name} loaded")
    log(f"[index] {sum(len(v) for v in by_ein.values()):,} 990/990EZ filings "
        f"across {len(by_ein):,} EINs")
    return by_ein, by_name


def match_and_fetchlist(conn: sqlite3.Connection, run_id: str,
                        index_dir: Path) -> None:
    by_ein, by_name = load_index(index_dir)
    # List B: unique normalized name in the index or nothing.
    unique = ambiguous = missing = 0
    for mention_id, name_norm in conn.execute(
        "SELECT target_key, name_norm FROM r990_targets "
        "WHERE identity_run_id=? AND target_list='B'", (run_id,)).fetchall():
        eins = by_name.get(name_norm, set())
        if len(eins) == 1:
            status, matched = "index_unique_name", next(iter(eins))
            unique += 1
        elif eins:
            status, matched = "index_ambiguous", None
            ambiguous += 1
        else:
            status, matched = "index_no_match", None
            missing += 1
        conn.execute(
            "UPDATE r990_targets SET match_status=?, matched_ein=? "
            "WHERE identity_run_id=? AND target_list='B' AND target_key=?",
            (status, matched, run_id, mention_id))
    log(f"[match] list B: {unique:,} unique-name, {ambiguous:,} ambiguous, "
        f"{missing:,} no index match")
    # Fetch list: every filing for every target EIN, deduped by object id.
    eins = {row[0] for row in conn.execute(
        "SELECT DISTINCT matched_ein FROM r990_targets "
        "WHERE identity_run_id=? AND matched_ein IS NOT NULL", (run_id,))}
    log(f"[dedup] distinct EINs to fetch: {len(eins):,}")
    inserted = 0
    for ein in eins:
        for object_id, ein_, rt, period, year, name in by_ein.get(ein, []):
            conn.execute(
                "INSERT OR IGNORE INTO r990_fetch_list VALUES (?,?,?,?,?,?,?,0)",
                (run_id, object_id, ein_, rt, period, year, name))
            inserted += 1
    conn.commit()
    total, with_filing = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT ein) FROM r990_fetch_list "
        "WHERE identity_run_id=?", (run_id,)).fetchone()
    log(f"[fetch-list] {total:,} filings to fetch covering {with_filing:,} EINs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants_v2.db"))
    parser.add_argument("--bmf-db", type=Path, default=Path("data/bmf_registry.db"))
    parser.add_argument("--index-dir", type=Path, default=Path("data/r990"))
    args = parser.parse_args()
    conn = sqlite3.connect(f"file:{args.db.resolve()}?mode=rw", uri=True, timeout=60)
    conn.execute("ATTACH DATABASE ? AS bmf",
                 (f"file:{args.bmf_db.resolve()}?mode=ro",))
    conn.executescript(SCHEMA)
    run_id = latest_run(conn)
    log(f"[run] building recipient-990 targets for {run_id}")
    build_lists(conn, run_id)
    match_and_fetchlist(conn, run_id, args.index_dir)
    conn.close()


if __name__ == "__main__":
    main()
