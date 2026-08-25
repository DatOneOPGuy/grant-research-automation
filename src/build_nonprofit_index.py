"""Browsable nonprofit table, baked into the read model.

    python3 -m src.build_nonprofit_index
    python3 -m src.build_nonprofit_index --db path.db --bmf path.db

Idempotent: drops and rebuilds. Re-run after any pipeline rebuild.

Why bake rather than join
-------------------------
The source is the IRS Business Master File, an 852 MB database that is not on
the droplet and is excluded from the code rsync. Joining it at query time would
make the feature undeployable. Flattening the fields we actually filter and
display into explorer_v5.db costs a few hundred MB and ships with the read
model, the same arrangement the search and sector indexes already use.

Who is in it
------------
Active 501(c)(3) public charities. Private foundations are excluded by
foundation_code -- they are already the subject of the rest of the product,
and mixing grantmakers into a list of grant-seekers would make both harder to
read.

Each row carries what the browser filters on -- NTEE major group, revenue
band, state -- plus what makes a row worth reading: how much this organisation
has received from majority-Christian foundations, and from how many, joined
from our own grant data where we have it.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

from src.sector_taxonomy import ntee_major, revenue_band

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "explorer_v5.db"
DEFAULT_BMF = ROOT / "data" / "bmf_registry.db"

CHUNK = 20_000
FOUNDATION_CODES = ("02", "03", "04")

# A funder is treated as Christian-leaning at 50% or more of classified giving.
# The threshold is a judgement, so it lives here named rather than inline.
CHRISTIAN_FUNDER_PCT = 50

SCHEMA = """
DROP TABLE IF EXISTS nonprofits;

CREATE TABLE nonprofits (
    ein            TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    city           TEXT,
    state          TEXT,
    ntee_code      TEXT,
    ntee_major     TEXT,
    revenue        INTEGER NOT NULL DEFAULT 0,
    revenue_band   INTEGER NOT NULL DEFAULT 0,
    assets         INTEGER NOT NULL DEFAULT 0,
    -- Enrichment from our own data, absent for organisations we have never
    -- seen receive a grant.
    tradition      TEXT,
    website        TEXT,
    mission        TEXT,
    christian_dollars INTEGER NOT NULL DEFAULT 0,
    christian_funders INTEGER NOT NULL DEFAULT 0
);
"""

INDEXES = """
CREATE INDEX idx_np_major ON nonprofits(ntee_major, revenue DESC);
CREATE INDEX idx_np_band ON nonprofits(revenue_band, revenue DESC);
CREATE INDEX idx_np_state ON nonprofits(state, revenue DESC);
CREATE INDEX idx_np_revenue ON nonprofits(revenue DESC);
CREATE INDEX idx_np_christian ON nonprofits(christian_dollars DESC);
CREATE INDEX idx_np_name ON nonprofits(name);

-- Partial indexes over the 47k organisations that have taken money from a
-- majority-Christian funder. Without them the "already Christian-funded"
-- filter groups from a full index but then reads the table once per row to
-- test the predicate: 600ms per facet against 1ms here. The subset is 3% of
-- the table, so three extra indexes cost almost nothing.
CREATE INDEX idx_np_chr_major ON nonprofits(ntee_major)
    WHERE christian_dollars > 0;
CREATE INDEX idx_np_chr_band ON nonprofits(revenue_band)
    WHERE christian_dollars > 0;
CREATE INDEX idx_np_chr_state ON nonprofits(state)
    WHERE christian_dollars > 0;
"""

SOURCE = f"""
SELECT ein, organization_name, city, state, ntee_code,
       income_amount, revenue_amount, asset_amount
FROM bmf_organizations
WHERE status_code = '01'
  AND subsection_code = '03'
  AND foundation_code NOT IN {FOUNDATION_CODES}
"""

ENRICH = f"""
SELECT rc.ein,
       rc.tradition,
       rc.website,
       SUBSTR(COALESCE(rc.mission_text, ''), 1, 400) AS mission,
       COALESCE(cf.dollars, 0) AS dollars,
       COALESCE(cf.funders, 0) AS funders
FROM recipients rc
LEFT JOIN (
    SELECT g.entity_id,
           SUM(g.amount) AS dollars,
           COUNT(DISTINCT g.funder_ein) AS funders
    FROM grants g
    JOIN foundations f ON f.ein = g.funder_ein
    WHERE f.pct_christian >= {CHRISTIAN_FUNDER_PCT}
    GROUP BY g.entity_id
) cf ON cf.entity_id = rc.entity_id
WHERE rc.ein IS NOT NULL AND rc.ein != ''
"""

PLACEHOLDERS = ("N/A", "NA", "NONE", "NULL", "")


def log(msg: str) -> None:
    print(f"[nonprofit-index] {msg}", flush=True)


def clean_website(raw: str | None) -> str | None:
    value = (raw or "").strip()
    if value.upper() in PLACEHOLDERS:
        return None
    # An email address in the website field is not a website.
    if "@" in value and "/" not in value:
        return None
    return value


def load_enrichment(conn: sqlite3.Connection) -> dict[str, tuple]:
    """ein -> (tradition, website, mission, christian_dollars, funders).

    Several recipient rows can share an EIN when identity resolution split an
    organisation; keep the one with the largest Christian relationship, since
    that is the row a reader would care about.
    """
    best: dict[str, tuple] = {}
    for ein, tradition, website, mission, dollars, funders in conn.execute(ENRICH):
        current = best.get(ein)
        if current is None or (dollars or 0) > current[3]:
            best[ein] = (tradition, clean_website(website), mission or None,
                         int(dollars or 0), int(funders or 0))
    return best


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

    # The build ends by switching journal mode back, which needs exclusive
    # access; a reader holding on makes that fail and leaves a -wal behind.
    try:
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        log("ERROR: the database is open elsewhere. Stop the API and any "
            "sqlite3 shells, then re-run.")
        conn.close()
        return 1

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-200000")
    conn.executescript(SCHEMA)

    step = time.monotonic()
    enrichment = load_enrichment(conn)
    log(f"enrichment for {len(enrichment):,} EINs "
        f"({time.monotonic() - step:.1f}s)")

    bmf = sqlite3.connect(f"file:{bmf_path}?mode=ro", uri=True)
    step = time.monotonic()
    cursor = bmf.execute(SOURCE)
    total = 0
    while True:
        chunk = cursor.fetchmany(CHUNK)
        if not chunk:
            break
        batch = []
        for (ein, name, city, state, ntee, income, revenue,
             assets) in chunk:
            # income_amount is gross receipts and is populated far more often
            # than revenue_amount; prefer the specific figure where it exists.
            amount = int(revenue or income or 0)
            extra = enrichment.get(ein, (None, None, None, 0, 0))
            batch.append((
                ein, (name or "").strip(), (city or "").strip() or None,
                (state or "").strip() or None, ntee or None, ntee_major(ntee),
                amount, revenue_band(amount), int(assets or 0),
                *extra,
            ))
        conn.executemany(
            "INSERT OR REPLACE INTO nonprofits (ein, name, city, state, "
            "ntee_code, ntee_major, revenue, revenue_band, assets, tradition, "
            "website, mission, christian_dollars, christian_funders) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
        total += len(batch)
    bmf.close()
    conn.commit()
    log(f"{total:,} nonprofits ({time.monotonic() - step:.1f}s)")

    step = time.monotonic()
    conn.executescript(INDEXES)
    conn.commit()
    log(f"indexed ({time.monotonic() - step:.1f}s)")

    with_christian = conn.execute(
        "SELECT COUNT(*) FROM nonprofits WHERE christian_dollars > 0"
    ).fetchone()[0]
    log(f"  {with_christian:,} have received money from a majority-Christian "
        "funder")

    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.close()
    log(f"done in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
