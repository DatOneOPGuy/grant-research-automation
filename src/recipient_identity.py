"""Resolve paid-grant recipient mentions conservatively against the full IRS BMF.

Rewritten after the first implementation ran 3h as one opaque atomic SQLite
transaction with Python UDFs invoked ~30M times. This version:
  - normalizes in Python (chunked, memoized) via src.identity_mentions
  - derives mentions/links/candidates/entities in pure indexed SQL
  - commits per phase with checkpoints; a killed run resumes losing at most
    one chunk; every phase logs progress and timing
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from src.bmf_registry import REQUIRED_FILES
from src.identity_mentions import (
    GRANT_NORM_SCHEMA,
    resume_point,
    scan_paid_grants,
)
from src.mention_disposition import annotate_status_buckets, apply_dispositions

ALGORITHM_VERSION = "exact-name-location-v3-dispositions"
ENTITY_STATUSES = ("matched_bmf", "collision", "unresolved", "unattributable",
                   "individual", "foreign", "government")
IDENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS identity_runs (
    run_id TEXT PRIMARY KEY,
    algorithm_version TEXT NOT NULL,
    bmf_source_digest TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recipient_mentions (
    run_id TEXT NOT NULL REFERENCES identity_runs(run_id),
    mention_id TEXT NOT NULL,
    name_norm TEXT NOT NULL,
    display_name TEXT,
    city_norm TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    raw_recipient_ein TEXT,
    grant_count INTEGER NOT NULL,
    paid_dollars INTEGER NOT NULL,
    max_paid_grant INTEGER NOT NULL,
    first_tax_year INTEGER,
    last_tax_year INTEGER,
    collision_flag INTEGER NOT NULL DEFAULT 0,
    status_bucket TEXT,
    disposition TEXT CHECK (disposition IN
        ('unattributable', 'individual', 'foreign', 'government')),
    PRIMARY KEY (run_id, mention_id)
);
CREATE TABLE IF NOT EXISTS grant_recipient_links (
    run_id TEXT NOT NULL,
    grant_id TEXT NOT NULL,
    mention_id TEXT NOT NULL,
    PRIMARY KEY (run_id, grant_id)
);
CREATE TABLE IF NOT EXISTS recipient_match_candidates (
    run_id TEXT NOT NULL,
    mention_id TEXT NOT NULL,
    candidate_ein TEXT NOT NULL,
    match_method TEXT NOT NULL,
    confidence REAL NOT NULL,
    match_rank INTEGER NOT NULL,
    selected INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, mention_id, candidate_ein)
);
CREATE TABLE IF NOT EXISTS recipient_entities (
    run_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    bmf_ein TEXT,
    canonical_name TEXT NOT NULL,
    identity_status TEXT NOT NULL
        CHECK (identity_status IN ('matched_bmf', 'collision', 'unresolved',
            'unattributable', 'individual', 'foreign', 'government')),
    PRIMARY KEY (run_id, entity_id)
);
CREATE TABLE IF NOT EXISTS recipient_entity_mentions (
    run_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    mention_id TEXT NOT NULL,
    PRIMARY KEY (run_id, mention_id)
);
CREATE INDEX IF NOT EXISTS idx_mentions_name_state
    ON recipient_mentions(run_id, name_norm, state, city_norm);
CREATE INDEX IF NOT EXISTS idx_candidates_mention
    ON recipient_match_candidates(run_id, mention_id, match_rank);
CREATE INDEX IF NOT EXISTS idx_entities_run_name
    ON recipient_entities(run_id, canonical_name);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity
    ON recipient_entity_mentions(run_id, entity_id);
CREATE TABLE IF NOT EXISTS identity_aliases (
    alias_norm TEXT NOT NULL,
    scope_state TEXT NOT NULL DEFAULT '',
    ein TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at_utc TEXT NOT NULL,
    PRIMARY KEY (alias_norm, scope_state)
);
"""


def migrate_legacy_tables(conn: sqlite3.Connection) -> None:
    """Rebuild derived identity tables when the status vocabulary grew.

    Everything dropped here is pipeline output, re-derived in minutes;
    identity_runs and identity_aliases are preserved as durable records.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='recipient_entities'"
    ).fetchone()
    if row is None or "unattributable" in (row[0] or ""):
        return
    _log("[migrate] entity status vocabulary changed; "
         "dropping derived identity tables for clean rebuild")
    for table in ("recipient_entity_mentions", "recipient_entities",
                  "recipient_match_candidates", "grant_recipient_links",
                  "recipient_mentions", "grant_norm", "identity_progress"):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants_v2.db"))
    parser.add_argument("--bmf-db", type=Path, default=Path("data/bmf_registry.db"))
    parser.add_argument("--run-id", default=None,
                        help="Resume an interrupted run by its run id.")
    return parser.parse_args()


def attach_registry(conn: sqlite3.Connection, path: Path) -> str:
    conn.execute("ATTACH DATABASE ? AS bmf", (f"file:{path.resolve()}?mode=ro",))
    rows = conn.execute(
        "SELECT source_file, source_sha256 FROM bmf.bmf_sources ORDER BY source_file"
    ).fetchall()
    if {row[0] for row in rows} != set(REQUIRED_FILES):
        raise RuntimeError("BMF registry does not contain all four required regions.")
    payload = "|".join(f"{name}:{digest}" for name, digest in rows)
    return hashlib.sha256(payload.encode()).hexdigest()


def phase_done(conn: sqlite3.Connection, run_id: str, phase: str) -> bool:
    return resume_point(conn, run_id, f"done:{phase}")[0] == -1


def mark_done(conn: sqlite3.Connection, run_id: str, phase: str, rows: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO identity_progress "
        "VALUES (?,?,-1,?,strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
        (run_id, f"done:{phase}", rows),
    )
    conn.commit()


def sql_phase(conn: sqlite3.Connection, run_id: str, phase: str,
              statements: list[tuple[str, tuple]]) -> None:
    """Run a pure-SQL phase once, with timing, commit, and done-marker."""
    if phase_done(conn, run_id, phase):
        _log(f"[{phase}] already complete, skipping")
        return
    started = time.monotonic()
    _log(f"[{phase}] starting")
    total = 0
    for sql, params in statements:
        cursor = conn.execute(sql, params)
        total += max(cursor.rowcount, 0)
    mark_done(conn, run_id, phase, total)
    _log(f"[{phase}] done: {total:,} rows in {time.monotonic() - started:,.1f}s")


def build_mentions(conn: sqlite3.Connection, run_id: str) -> None:
    sql_phase(conn, run_id, "mentions", [(
        """
        INSERT OR IGNORE INTO recipient_mentions
          (run_id, mention_id, name_norm, display_name, city_norm, city,
           state, country, raw_recipient_ein, grant_count, paid_dollars,
           max_paid_grant, first_tax_year, last_tax_year, collision_flag)
        SELECT run_id, mention_id, name_norm, MAX(display_name),
               city_norm, MAX(city), state, country,
               MAX(NULLIF(raw_recipient_ein,'')),
               COUNT(*), SUM(signed_amount), MAX(signed_amount),
               MIN(tax_year), MAX(tax_year), 0
        FROM grant_norm WHERE run_id=?
        GROUP BY mention_id
        """, (run_id,),
    )])
    sql_phase(conn, run_id, "links", [(
        "INSERT OR IGNORE INTO grant_recipient_links "
        "SELECT run_id, grant_id, mention_id FROM grant_norm WHERE run_id=?",
        (run_id,),
    )])


def run_dispositions(conn: sqlite3.Connection, run_id: str) -> None:
    if phase_done(conn, run_id, "dispositions"):
        _log("[dispositions] already complete, skipping")
        return
    started = time.monotonic()
    annotate_status_buckets(conn, run_id)
    counts = apply_dispositions(conn, run_id)
    mark_done(conn, run_id, "dispositions", sum(counts.values()))
    _log(f"[dispositions] phase done in {time.monotonic() - started:,.1f}s")


def build_candidates(conn: sqlite3.Connection, run_id: str) -> None:
    # Human-approved aliases outrank everything: asserted facts, not matches.
    sql_phase(conn, run_id, "candidates_alias", [(
        """
        INSERT OR IGNORE INTO recipient_match_candidates
        SELECT m.run_id, m.mention_id, a.ein, 'human_alias', 1.00, 0, 0
        FROM recipient_mentions m
        JOIN identity_aliases a ON a.alias_norm = m.name_norm
          AND (a.scope_state = '' OR a.scope_state = m.state)
        JOIN bmf.bmf_organizations b ON b.ein = a.ein
        WHERE m.run_id=? AND m.disposition IS NULL
        """, (run_id,),
    )])
    # Reported-EIN pass runs on its own join key, so a filed EIN matches
    # even when the recipient's name string does not (the prior version
    # required both, making the EIN tier unreachable).
    sql_phase(conn, run_id, "candidates_ein", [(
        """
        INSERT OR IGNORE INTO recipient_match_candidates
        SELECT m.run_id, m.mention_id, b.ein, 'reported_ein', 1.00, 1, 0
        FROM recipient_mentions m
        JOIN bmf.bmf_organizations b ON b.ein = m.raw_recipient_ein
        WHERE m.run_id=? AND m.raw_recipient_ein IS NOT NULL
          AND m.disposition IS NULL
        """, (run_id,),
    )])
    sql_phase(conn, run_id, "candidates_name", [(
        """
        INSERT OR IGNORE INTO recipient_match_candidates
        SELECT m.run_id, m.mention_id, b.ein,
               CASE WHEN m.state != '' AND m.city_norm != ''
                         AND m.state = b.state AND m.city_norm = b.city_norm
                      THEN 'exact_name_city_state'
                    WHEN m.state != '' AND m.state = b.state
                      THEN 'exact_name_state'
                    ELSE 'exact_name_national' END,
               CASE WHEN m.state != '' AND m.city_norm != ''
                         AND m.state = b.state AND m.city_norm = b.city_norm
                      THEN 0.99
                    WHEN m.state != '' AND m.state = b.state THEN 0.95
                    ELSE 0.90 END,
               CASE WHEN m.state != '' AND m.city_norm != ''
                         AND m.state = b.state AND m.city_norm = b.city_norm
                      THEN 2
                    WHEN m.state != '' AND m.state = b.state THEN 3
                    ELSE 4 END,
               0
        FROM recipient_mentions m
        JOIN bmf.bmf_organizations b ON b.name_norm = m.name_norm
        WHERE m.run_id=? AND m.name_norm != '' AND m.disposition IS NULL
        """, (run_id,),
    )])
    build_variant_candidates(conn, run_id)


def build_variant_candidates(conn: sqlite3.Connection, run_id: str) -> None:
    """Suffix/prefix variant tier — below all exact tiers, gated on precision.

    Variants are computed on the mention side so the BMF name index stays
    usable. State agreement is required (rank 5, 0.97); blank-state mentions
    may match nationally (rank 6, 0.95) where unique-best still applies.
    """
    variants = [
        ("inc_added", "m.name_norm || ' inc'", "1"),
        ("inc_removed", "substr(m.name_norm, 1, length(m.name_norm)-4)",
         "m.name_norm LIKE '% inc'"),
        ("the_removed", "substr(m.name_norm, 5)", "m.name_norm LIKE 'the %'"),
        ("the_added", "'the ' || m.name_norm", "1"),
        # Word-form family (integrity check A): filers abbreviate what the
        # BMF spells out and vice versa — 'INDIANA ASSOCIATION OF UNITED
        # WAYS' vs BMF '... INCORPORATED'.
        ("incorporated_added", "m.name_norm || ' incorporated'", "1"),
        ("inc_to_incorporated",
         "substr(m.name_norm, 1, length(m.name_norm)-4) || ' incorporated'",
         "m.name_norm LIKE '% inc'"),
        ("incorporated_to_inc",
         "substr(m.name_norm, 1, length(m.name_norm)-13) || ' inc'",
         "m.name_norm LIKE '% incorporated'"),
        ("corporation_added", "m.name_norm || ' corporation'", "1"),
        ("corp_to_corporation",
         "substr(m.name_norm, 1, length(m.name_norm)-5) || ' corporation'",
         "m.name_norm LIKE '% corp'"),
    ]
    statements = []
    for label, expr, guard in variants:
        statements.append((f"""
            INSERT OR IGNORE INTO recipient_match_candidates
            SELECT m.run_id, m.mention_id, b.ein,
                   'variant_{label}_state', 0.97, 5, 0
            FROM recipient_mentions m
            JOIN bmf.bmf_organizations b
              ON b.name_norm = {expr} AND b.state = m.state
            WHERE m.run_id=? AND m.disposition IS NULL AND m.state != ''
              AND {guard}
        """, (run_id,)))
        statements.append((f"""
            INSERT OR IGNORE INTO recipient_match_candidates
            SELECT m.run_id, m.mention_id, b.ein,
                   'variant_{label}_national', 0.95, 6, 0
            FROM recipient_mentions m
            JOIN bmf.bmf_organizations b ON b.name_norm = {expr}
            WHERE m.run_id=? AND m.disposition IS NULL AND m.state = ''
              AND {guard}
        """, (run_id,)))
    sql_phase(conn, run_id, "candidates_variant", statements)


def select_unambiguous(conn: sqlite3.Connection, run_id: str) -> None:
    sql_phase(conn, run_id, "selection", [
        ("""
        WITH best AS (
          SELECT mention_id, MIN(match_rank) AS best_rank
          FROM recipient_match_candidates WHERE run_id=? GROUP BY mention_id
        ), unique_best AS (
          SELECT c.mention_id, c.match_rank
          FROM recipient_match_candidates c JOIN best b
            ON b.mention_id=c.mention_id AND b.best_rank=c.match_rank
          WHERE c.run_id=? GROUP BY c.mention_id, c.match_rank HAVING COUNT(*)=1
        )
        UPDATE recipient_match_candidates AS c SET selected=1
        WHERE c.run_id=? AND EXISTS (
          SELECT 1 FROM unique_best u
          WHERE u.mention_id=c.mention_id AND u.match_rank=c.match_rank)
        """, (run_id, run_id, run_id)),
        ("""
        WITH best AS (
          SELECT mention_id, MIN(match_rank) AS best_rank
          FROM recipient_match_candidates WHERE run_id=? GROUP BY mention_id
        ), collisions AS (
          SELECT c.mention_id
          FROM recipient_match_candidates c JOIN best b
            ON b.mention_id=c.mention_id AND b.best_rank=c.match_rank
          WHERE c.run_id=? GROUP BY c.mention_id HAVING COUNT(*)>1
        )
        UPDATE recipient_mentions SET collision_flag=1
        WHERE run_id=? AND mention_id IN (SELECT mention_id FROM collisions)
        """, (run_id, run_id, run_id)),
    ])


def create_entities(conn: sqlite3.Connection, run_id: str) -> None:
    sql_phase(conn, run_id, "entities", [
        ("""
        INSERT OR IGNORE INTO recipient_entities
        SELECT ?, COALESCE('ein:' || c.candidate_ein, 'mention:' || m.mention_id),
               c.candidate_ein, COALESCE(b.organization_name, m.display_name),
               CASE WHEN m.disposition IS NOT NULL THEN m.disposition
                    WHEN c.candidate_ein IS NOT NULL THEN 'matched_bmf'
                    WHEN m.collision_flag=1 THEN 'collision' ELSE 'unresolved' END
        FROM recipient_mentions m
        LEFT JOIN recipient_match_candidates c
          ON c.run_id=m.run_id AND c.mention_id=m.mention_id AND c.selected=1
        LEFT JOIN bmf.bmf_organizations b ON b.ein=c.candidate_ein
        WHERE m.run_id=? GROUP BY 2
        """, (run_id, run_id)),
        ("""
        INSERT OR IGNORE INTO recipient_entity_mentions
        SELECT ?, COALESCE('ein:' || c.candidate_ein, 'mention:' || m.mention_id),
               m.mention_id
        FROM recipient_mentions m
        LEFT JOIN recipient_match_candidates c
          ON c.run_id=m.run_id AND c.mention_id=m.mention_id AND c.selected=1
        WHERE m.run_id=?
        """, (run_id, run_id)),
    ])


def report(conn: sqlite3.Connection, run_id: str) -> None:
    print(f"Identity run: {run_id}")
    for status, entities, mentions, dollars in conn.execute(
        """
        SELECT e.identity_status, COUNT(DISTINCT e.entity_id),
               COUNT(m.mention_id), SUM(m.paid_dollars)
        FROM recipient_entities e
        JOIN recipient_entity_mentions em
          ON em.run_id=e.run_id AND em.entity_id=e.entity_id
        JOIN recipient_mentions m
          ON m.run_id=em.run_id AND m.mention_id=em.mention_id
        WHERE e.run_id=? GROUP BY 1 ORDER BY 1
        """, (run_id,),
    ):
        print(f"  {status}: {entities:,} entities | {mentions:,} mentions "
              f"| ${dollars/1e9:,.2f}B paid")
    print("By match method:")
    for method, count, dollars in conn.execute(
        """
        SELECT c.match_method, COUNT(*), SUM(m.paid_dollars)
        FROM recipient_match_candidates c
        JOIN recipient_mentions m
          ON m.run_id=c.run_id AND m.mention_id=c.mention_id
        WHERE c.run_id=? AND c.selected=1 GROUP BY 1 ORDER BY 3 DESC
        """, (run_id,),
    ):
        print(f"  {method}: {count:,} | ${dollars/1e9:,.2f}B")


def run(db_path: Path, bmf_path: Path, run_id: str | None = None) -> str:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=rw", uri=True, timeout=60)
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-524288")
    migrate_legacy_tables(conn)
    conn.executescript(IDENTITY_SCHEMA)
    conn.executescript(GRANT_NORM_SCHEMA)
    digest = attach_registry(conn, bmf_path)
    if run_id is None:
        run_id = datetime.now(UTC).strftime("identity-%Y%m%dT%H%M%SZ")
        conn.execute(
            "INSERT INTO identity_runs VALUES (?,?,?,?)",
            (run_id, ALGORITHM_VERSION, digest, datetime.now(UTC).isoformat()),
        )
        conn.commit()
        _log(f"[run] new identity run {run_id}")
    else:
        row = conn.execute(
            "SELECT bmf_source_digest FROM identity_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise SystemExit(f"No identity run named {run_id!r} to resume.")
        if row[0] != digest:
            raise SystemExit("BMF registry changed since this run started; "
                             "start a fresh run instead of resuming.")
        _log(f"[run] resuming identity run {run_id}")
    if not phase_done(conn, run_id, "scan"):
        rows = scan_paid_grants(conn, run_id)
        mark_done(conn, run_id, "scan", rows)
    build_mentions(conn, run_id)
    run_dispositions(conn, run_id)
    build_candidates(conn, run_id)
    select_unambiguous(conn, run_id)
    create_entities(conn, run_id)
    report(conn, run_id)
    conn.close()
    return run_id


def main() -> None:
    args = parse_args()
    run(args.db, args.bmf_db, args.run_id)


if __name__ == "__main__":
    main()
