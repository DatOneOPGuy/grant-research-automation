"""Full-text search index for the Explorer read model.

Builds FTS5 tables alongside the existing explorer_v5.db tables. Idempotent:
drops and rebuilds, so it can be re-run after any pipeline rebuild.

    python3 -m src.build_search_index                 # data/explorer_v5.db
    python3 -m src.build_search_index --db path.db

Why three tables rather than one row per foundation
---------------------------------------------------
The obvious shape is one FTS row per foundation with every recipient name,
mission and grant purpose concatenated into it. That makes the query a single
MATCH, but it duplicates each recipient's mission once per funder that gave to
them -- measured at 104 MB of mission text against 9 MB of distinct text, an
11x blowup -- and it throws away the identity of what matched. "A recipient
matched" is a much worse answer than "Young Life matched", and the second is
what makes the result explainable.

So recipients are indexed once, and the join back to funders goes through
grants(entity_id), which is already indexed. The cost is one extra lookup per
search; the benefit is a third of the index size and an attribution trail.

Tokenizer: porter stemming so "ministries" finds "ministry", and unicode61
with diacritic folding so "Peña" matches "Pena". Foundation names additionally
carry a prefix index for typeahead, which is the only column where a user
expects results before they finish typing a word.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "explorer_v5.db"

# Chunk size for executemany. Large enough to amortise the round trip, small
# enough that the transaction does not balloon the WAL -- see the operational
# rules in the project notes: a multi-GB WAL is how the last corruption began.
CHUNK = 20_000

TOKENIZE = "porter unicode61 remove_diacritics 2"

SCHEMA = f"""
DROP TABLE IF EXISTS search_foundation;
DROP TABLE IF EXISTS search_recipient;
DROP TABLE IF EXISTS search_purpose;
DROP TABLE IF EXISTS search_meta;

-- One row per foundation. prefix='2 3 4' powers typeahead on names only.
CREATE VIRTUAL TABLE search_foundation USING fts5(
    ein UNINDEXED,
    name,
    location,
    tokenize = '{TOKENIZE}',
    prefix = '2 3 4'
);

-- One row per recipient, indexed once regardless of how many funders gave to
-- them. Joined back to foundations through search_edge at query time.
--
-- The prefix index matters as much here as on foundation names: without it a
-- trailing wildcard has to walk the term list of a 1.3M-row index, which
-- measured at 44 ms against 7 ms for the prefixed foundation table.
CREATE VIRTUAL TABLE search_recipient USING fts5(
    entity_id UNINDEXED,
    name,
    mission,
    tokenize = '{TOKENIZE}',
    prefix = '2 3 4'
);

-- Grant purposes, aggregated per funder. Unlike a recipient, a purpose string
-- has no entity worth naming in the UI, so there is nothing lost by folding
-- them together and a 3M-row index avoided.
CREATE VIRTUAL TABLE search_purpose USING fts5(
    ein UNINDEXED,
    purpose,
    tokenize = '{TOKENIZE}'
);

-- Funder <- grantee edges, rolled up once at build time.
--
-- Search needs "which foundations funded these grantees, biggest first". Doing
-- that as a GROUP BY over the 3M-row grants table cost 53 ms per search, which
-- was the single largest component of query latency. Precomputed it is an
-- indexed range scan over 2M narrow rows.
CREATE TABLE search_edge (
    entity_id TEXT NOT NULL,
    funder_ein TEXT NOT NULL,
    dollars REAL NOT NULL
);

CREATE TABLE search_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

EDGE_INDEX = """
CREATE INDEX idx_search_edge ON search_edge(entity_id, dollars DESC);
"""


def log(msg: str) -> None:
    print(f"[search-index] {msg}", flush=True)


def chunked(cursor, size: int = CHUNK):
    while True:
        rows = cursor.fetchmany(size)
        if not rows:
            return
        yield rows


def build_foundations(conn: sqlite3.Connection) -> int:
    src = conn.execute("""
        SELECT ein,
               COALESCE(name, ''),
               TRIM(COALESCE(city, '') || ' ' || COALESCE(state, ''))
        FROM foundations
    """)
    total = 0
    for rows in chunked(src):
        conn.executemany(
            "INSERT INTO search_foundation(ein, name, location) VALUES (?,?,?)",
            rows)
        total += len(rows)
    return total


def build_recipients(conn: sqlite3.Connection) -> int:
    # display_name first: it is the cleaned identity, and falling back to the
    # raw name keeps recipients searchable even where identity resolution
    # could not produce one. Placeholder strings like "GRANTS" are already
    # handled upstream by display_name.
    src = conn.execute("""
        SELECT entity_id,
               COALESCE(NULLIF(display_name, ''), name, ''),
               COALESCE(mission_text, '')
        FROM recipients
        WHERE COALESCE(NULLIF(display_name, ''), name, '') != ''
           OR COALESCE(mission_text, '') != ''
    """)
    total = 0
    for rows in chunked(src):
        conn.executemany(
            "INSERT INTO search_recipient(entity_id, name, mission) "
            "VALUES (?,?,?)", rows)
        total += len(rows)
    return total


def build_purposes(conn: sqlite3.Connection) -> int:
    # DISTINCT because funders repeat the same boilerplate purpose across
    # hundreds of grants; indexing it once per funder is enough to match on.
    src = conn.execute("""
        SELECT funder_ein, GROUP_CONCAT(purpose, ' ')
        FROM (
            SELECT DISTINCT funder_ein, purpose
            FROM grants
            WHERE purpose IS NOT NULL AND purpose != ''
        )
        GROUP BY funder_ein
    """)
    total = 0
    for rows in chunked(src, 2_000):
        conn.executemany(
            "INSERT INTO search_purpose(ein, purpose) VALUES (?,?)", rows)
        total += len(rows)
    return total


def build_edges(conn: sqlite3.Connection) -> int:
    src = conn.execute("""
        SELECT entity_id, funder_ein, SUM(amount)
        FROM grants
        WHERE entity_id IS NOT NULL AND funder_ein IS NOT NULL
        GROUP BY entity_id, funder_ein
    """)
    total = 0
    for rows in chunked(src):
        conn.executemany(
            "INSERT INTO search_edge(entity_id, funder_ein, dollars) "
            "VALUES (?,?,?)", rows)
        total += len(rows)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        log(f"ERROR: no such database: {db_path}")
        return 1

    started = time.monotonic()
    conn = sqlite3.connect(db_path)
    # Speed knobs for a bulk build. synchronous=OFF is safe here because the
    # index is derived: if the machine dies mid-build, re-run the script.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-200000")  # ~200 MB

    log(f"building into {db_path}")
    conn.executescript(SCHEMA)

    for label, fn in (("foundations", build_foundations),
                      ("recipients", build_recipients),
                      ("purposes", build_purposes),
                      ("edges", build_edges)):
        step = time.monotonic()
        count = fn(conn)
        conn.commit()
        log(f"{label}: {count:,} rows in {time.monotonic() - step:.1f}s")

    step = time.monotonic()
    conn.executescript(EDGE_INDEX)
    conn.commit()
    log(f"indexed search_edge in {time.monotonic() - step:.1f}s")

    for label in ("search_foundation", "search_recipient", "search_purpose"):
        step = time.monotonic()
        conn.execute(f"INSERT INTO {label}({label}) VALUES('optimize')")
        conn.commit()
        log(f"optimised {label} in {time.monotonic() - step:.1f}s")

    conn.execute(
        "INSERT OR REPLACE INTO search_meta(key, value) VALUES ('built_at', ?)",
        (time.strftime("%Y-%m-%dT%H:%M:%S"),))
    conn.commit()

    # Checkpoint and drop the WAL before anything else opens this file. A
    # leftover multi-GB -wal following the filename through a later move is
    # exactly how this project corrupted a database once already.
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.close()

    log(f"done in {time.monotonic() - started:.1f}s")
    for sidecar in (db_path.with_suffix(db_path.suffix + "-wal"),
                    db_path.with_suffix(db_path.suffix + "-shm")):
        if sidecar.exists():
            log(f"WARNING: {sidecar.name} still present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
