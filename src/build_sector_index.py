"""Classify non-Christian giving by cause area, and roll it up per foundation.

    python3 -m src.build_sector_index
    python3 -m src.build_sector_index --db path.db --bmf path.db

Idempotent: drops and rebuilds its two tables, so it can re-run after any
pipeline rebuild. Adds nothing to the Christian side of the ledger and
changes no existing column -- the read model's own numbers are untouched.

    recipient_sectors(entity_id, sector, method, confidence, ntee_code)
    sector_stats(ein, sector, tier, dollars, recipients, grants)

sector_stats mirrors tradition_stats exactly, including the authoritative
tier, so the two can be queried and presented the same way.

Assignment precedence, strongest evidence first:

  1. the pipeline's own religious classification, for non-Christian faiths
  2. NTEE code from the IRS Business Master File, joined on EIN
  3. NTEE code from the BMF, joined on normalised name, and only where every
     BMF row with that name agrees on the major group
  4. a conservative keyword rule over the recipient's name
  5. unknown

Step 3 exists because the largest uncoded recipients are EIN collisions --
"johns hopkins university", "yale university" -- where the name is perfectly
well known and only the identifier is ambiguous. Step 4 is the weakest and is
labelled 'low' confidence wherever it surfaces.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

from src.identity_normalize import normalize_identity_name
from src.sector_taxonomy import (
    METHOD_CONFIDENCE,
    TRADITION_SECTOR,
    sector_from_name,
    sector_from_ntee,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "explorer_v5.db"
DEFAULT_BMF = ROOT / "data" / "bmf_registry.db"

CHUNK = 20_000

# Traditions that make up the non-Christian bucket, matching the definition
# in build_explorer_v5.py. Kept in one place here so the two cannot drift
# apart silently.
NONCHRISTIAN_TRADITIONS = (
    "jewish", "muslim", "mormon_lds", "christian_science",
    "other_religion", "secular", "nonchristian_unspecified",
)

# Methods the read model treats as authoritative for the tighter tier.
AUTHORITATIVE_METHODS = ("rule", "ntee", "church_code_name", "group_exemption")

SCHEMA = """
DROP TABLE IF EXISTS recipient_sectors;
DROP TABLE IF EXISTS sector_stats;

CREATE TABLE recipient_sectors (
    entity_id  TEXT PRIMARY KEY,
    sector     TEXT NOT NULL,
    method     TEXT,
    confidence TEXT,
    ntee_code  TEXT
);

CREATE TABLE sector_stats (
    ein        TEXT NOT NULL,
    sector     TEXT NOT NULL,
    tier       TEXT NOT NULL,
    dollars    INTEGER NOT NULL,
    recipients INTEGER NOT NULL,
    grants     INTEGER NOT NULL,
    PRIMARY KEY (ein, sector, tier)
);
"""

INDEXES = """
CREATE INDEX idx_rs_sector ON recipient_sectors(sector);
CREATE INDEX idx_ss_ein ON sector_stats(ein, tier, dollars DESC);
CREATE INDEX idx_ss_sector ON sector_stats(sector, tier, dollars DESC);
"""


def log(msg: str) -> None:
    print(f"[sector-index] {msg}", flush=True)


def load_ntee_by_ein(bmf: sqlite3.Connection) -> dict[str, str]:
    return {
        ein: code for ein, code in bmf.execute(
            "SELECT ein, ntee_code FROM bmf_organizations "
            "WHERE ntee_code IS NOT NULL AND ntee_code != ''")
    }


def load_ntee_by_name(bmf: sqlite3.Connection) -> dict[str, str]:
    """Normalised name -> NTEE code, keeping only unambiguous names.

    A name whose BMF rows disagree about the major group tells us nothing, so
    it is dropped rather than resolved by picking one. 12,023 names out of
    1.3M are ambiguous in this sense.
    """
    best: dict[str, str] = {}
    ambiguous: set[str] = set()
    for name, code in bmf.execute(
            "SELECT name_norm, ntee_code FROM bmf_organizations "
            "WHERE ntee_code IS NOT NULL AND ntee_code != '' "
            "AND name_norm IS NOT NULL AND name_norm != ''"):
        if name in ambiguous:
            continue
        existing = best.get(name)
        if existing is None:
            best[name] = code
        elif existing[:1].upper() != code[:1].upper():
            del best[name]
            ambiguous.add(name)
    return best


def classify(conn: sqlite3.Connection, by_ein: dict[str, str],
             by_name: dict[str, str]) -> dict[str, int]:
    """Assign a sector to every recipient in the non-Christian bucket."""
    placeholders = ",".join("?" for _ in NONCHRISTIAN_TRADITIONS)
    rows = conn.execute(f"""
        SELECT entity_id, ein, tradition,
               COALESCE(NULLIF(display_name, ''), name, '') AS nm
        FROM recipients
        WHERE tradition IN ({placeholders}) AND is_daf = 0
    """, NONCHRISTIAN_TRADITIONS)

    counts: dict[str, int] = {}
    batch: list[tuple] = []
    total = 0
    while True:
        chunk = rows.fetchmany(CHUNK)
        if not chunk:
            break
        for entity_id, ein, tradition, nm in chunk:
            sector = method = ntee = None

            faith = TRADITION_SECTOR.get(tradition or "")
            if faith:
                sector, method = faith, "tradition"
            else:
                ntee = by_ein.get(ein) if ein else None
                if ntee:
                    sector = sector_from_ntee(ntee)
                    method = "ntee_ein" if sector else None
                if not sector and nm:
                    key = normalize_identity_name(nm)
                    candidate = by_name.get(key) if key else None
                    if candidate:
                        sector = sector_from_ntee(candidate)
                        if sector:
                            ntee, method = candidate, "ntee_name"
                if not sector:
                    sector = sector_from_name(nm)
                    method = "name_rule" if sector else None

            if not sector:
                sector, method = "unknown", None

            counts[sector] = counts.get(sector, 0) + 1
            batch.append((entity_id, sector, method,
                          METHOD_CONFIDENCE.get(method or ""), ntee))
            total += 1

        conn.executemany(
            "INSERT OR REPLACE INTO recipient_sectors"
            "(entity_id, sector, method, confidence, ntee_code) "
            "VALUES (?,?,?,?,?)", batch)
        batch.clear()

    log(f"classified {total:,} recipients")
    return counts


def rollup(conn: sqlite3.Connection) -> int:
    """Per-foundation dollars by sector, on both tiers.

    'all' counts every classified grant; 'authoritative' restricts to the
    same methods the read model already treats as authoritative for its
    tighter Christian figure, so the two tiers stay comparable.
    """
    conn.execute("""
        INSERT INTO sector_stats(ein, sector, tier, dollars, recipients, grants)
        SELECT g.funder_ein, s.sector, 'all',
               CAST(SUM(g.amount) AS INTEGER),
               COUNT(DISTINCT g.entity_id), COUNT(*)
        FROM grants g
        JOIN recipient_sectors s ON s.entity_id = g.entity_id
        GROUP BY g.funder_ein, s.sector
    """)
    conn.execute(f"""
        INSERT INTO sector_stats(ein, sector, tier, dollars, recipients, grants)
        SELECT g.funder_ein, s.sector, 'authoritative',
               CAST(SUM(g.amount) AS INTEGER),
               COUNT(DISTINCT g.entity_id), COUNT(*)
        FROM grants g
        JOIN recipient_sectors s ON s.entity_id = g.entity_id
        JOIN recipients r ON r.entity_id = g.entity_id
        WHERE r.method IN {AUTHORITATIVE_METHODS}
        GROUP BY g.funder_ein, s.sector
    """)
    return conn.execute("SELECT COUNT(*) FROM sector_stats").fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--bmf", default=str(DEFAULT_BMF))
    args = parser.parse_args()

    db_path, bmf_path = Path(args.db), Path(args.bmf)
    for path in (db_path, bmf_path):
        if not path.exists():
            log(f"ERROR: no such database: {path}")
            return 1

    started = time.monotonic()
    conn = sqlite3.connect(db_path)

    # Refuse to start if anything else has the database open. The build ends
    # by switching the journal mode back, which needs exclusive access; a
    # reader holding on -- a running uvicorn, a forgotten sqlite3 shell --
    # makes that final step fail and leaves a -wal behind. Sidecars follow
    # the filename rather than the file, so a stray -wal surviving into a
    # later move is how this project corrupted a database once already.
    try:
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        log("ERROR: the database is open elsewhere. Stop the API "
            "(systemctl stop fcf, or the local uvicorn) and any sqlite3 "
            "shells, then re-run. Refusing to start rather than finish in a "
            "state that cannot be checkpointed.")
        conn.close()
        return 1

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-200000")
    conn.executescript(SCHEMA)

    bmf = sqlite3.connect(f"file:{bmf_path}?mode=ro", uri=True)
    step = time.monotonic()
    by_ein = load_ntee_by_ein(bmf)
    by_name = load_ntee_by_name(bmf)
    bmf.close()
    log(f"BMF: {len(by_ein):,} NTEE by EIN, {len(by_name):,} unambiguous "
        f"by name ({time.monotonic() - step:.1f}s)")

    step = time.monotonic()
    counts = classify(conn, by_ein, by_name)
    conn.commit()
    log(f"classification took {time.monotonic() - step:.1f}s")

    step = time.monotonic()
    rows = rollup(conn)
    conn.executescript(INDEXES)
    conn.commit()
    log(f"rolled up {rows:,} (ein, sector, tier) rows "
        f"({time.monotonic() - step:.1f}s)")

    for sector, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        log(f"  {sector:24} {n:>8,} recipients")

    # Checkpoint before anything else opens the file: sidecars follow the
    # filename, and a stray -wal is how this project corrupted a db before.
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.close()
    log(f"done in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
