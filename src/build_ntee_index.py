"""Build the NTEE rollup for the read model.

    python3 -m src.build_ntee_index

One table, foundation_ntee: which NTEE codes each foundation's grantees
carry, BY STATE, with dollars. The state dimension is the point — Emily's
request (2026-09-24) is conjoint: "food security in North Carolina", "youth
camps in these 12 states". Grants to a K-coded org in NC are a different
fact from funding K somewhere and NC somewhere, and only the first is a
lead. Instrumentl cannot ask this question; this table exists so we can.

State is the grant's recipient state where it is a US state/territory code,
else '' — the empty bucket keeps pure cause-area filtering complete while
the conjoint filter matches only real states.

Codes come from the recipients -> nonprofits join (both already in the read
model; the BMF itself is not on the droplet and must not be needed at
query time). Coverage is honest and partial: only EIN-matched recipients
carry a code — 202,838 recipients, $77.6B of $236.4B in grant dollars (33%)
at build time. The filter means "has at least one coded grantee matching",
never "all of its giving is X" — the UI says so.

Codes are stored uppercased and trimmed but otherwise raw ('B21', 'A69Z',
'E220'): filtering is by prefix, so majors ('B') and full codes ('B21')
work through one LIKE.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "explorer_v5.db"

# Same US set recipient_states uses (50 + DC + territories + AA/AE/AP).
US_STATES = frozenset("""
    AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS
    MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV
    WI WY DC PR VI GU AS MP AA AE AP
""".split())

SCHEMA = """
DROP TABLE IF EXISTS foundation_ntee;
CREATE TABLE foundation_ntee (
    ein     TEXT NOT NULL,
    ntee    TEXT NOT NULL,
    state   TEXT NOT NULL,   -- US state the grant went to, or ''
    dollars INTEGER NOT NULL,
    grants  INTEGER NOT NULL,
    PRIMARY KEY (ein, ntee, state)
);
"""
INDEXES = """
DROP INDEX IF EXISTS idx_ntee_code;
CREATE INDEX idx_ntee_code ON foundation_ntee(ntee, state, dollars DESC);
"""


def log(msg: str) -> None:
    print(f"[ntee-index] {msg}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    db = Path(args.db)
    if not db.exists():
        log(f"ERROR: no such database: {db}")
        return 1

    started = time.monotonic()
    conn = sqlite3.connect(db)
    try:
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        log("ERROR: the database is open elsewhere. Stop the API and re-run.")
        conn.close()
        return 1

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.executescript(SCHEMA)

    marks = ",".join(f"'{s}'" for s in sorted(US_STATES))
    conn.execute(f"""
        INSERT INTO foundation_ntee (ein, ntee, state, dollars, grants)
        SELECT g.funder_ein, UPPER(TRIM(n.ntee_code)),
               CASE WHEN UPPER(TRIM(COALESCE(g.recipient_state,'')))
                         IN ({marks})
                    THEN UPPER(TRIM(g.recipient_state)) ELSE '' END,
               SUM(g.amount), COUNT(*)
        FROM grants g
        JOIN recipients r ON r.entity_id = g.entity_id
        JOIN nonprofits n ON n.ein = r.ein
        WHERE COALESCE(n.ntee_code, '') != ''
        GROUP BY 1, 2, 3
    """)  # noqa: S608 — marks is a literal frozenset above, not input
    conn.executescript(INDEXES)
    conn.commit()

    rows = conn.execute("SELECT COUNT(*) FROM foundation_ntee").fetchone()[0]
    funders = conn.execute(
        "SELECT COUNT(DISTINCT ein) FROM foundation_ntee").fetchone()[0]
    dollars = conn.execute(
        "SELECT SUM(dollars) FROM foundation_ntee").fetchone()[0]
    codes = conn.execute(
        "SELECT COUNT(DISTINCT ntee) FROM foundation_ntee").fetchone()[0]
    stated = conn.execute(
        "SELECT SUM(dollars) FROM foundation_ntee WHERE state != ''"
    ).fetchone()[0]
    log(f"{rows:,} (funder, code, state) rows | {funders:,} foundations | "
        f"{codes:,} codes | ${dollars/1e9:.1f}B attributed "
        f"(${stated/1e9:.1f}B with a US state)")

    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.close()
    log(f"done in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
