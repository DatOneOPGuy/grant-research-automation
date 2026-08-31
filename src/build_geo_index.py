"""Build the county rollup for the read model.

    python3 -m src.build_geo_index

Adds two tables. foundation_counties mirrors recipient_states one level down:
where a funder's money went. recipient_counties answers the other question --
where a recipient IS -- which has to be derived, because the recipients table
carries no address at all. Regions need no table; they are a mapping over the
state code and live in backend/regions.py.

Counties are matched from the city on the filing against two Census files:
places (32,188 of them) and county subdivisions, which is where the townships
that New Jersey and Pennsylvania file against live. Places win ties, since a
filing naming "Princeton" means the town far more often than the township
surrounding it.

88.8% of US grant dollars and 91.2% of recipients match. The remainder is
filings that wrote "VARIOUS", "NA" or "See Attached" in the city field; those
are left unplaced rather than guessed at, and a county filter simply will not
return them.
"""

from __future__ import annotations

import argparse
import collections
import csv
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

from src.geo_regions import (
    is_placeholder,
    place_alias,
    place_key,
    place_keys,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "explorer_v5.db"
CACHE = ROOT / "data" / "census"

SOURCES = {
    "place2020.txt":
        "https://www2.census.gov/geo/docs/reference/codes2020/"
        "national_place2020.txt",
    "cousub2020.txt":
        "https://www2.census.gov/geo/docs/reference/codes2020/"
        "national_cousub2020.txt",
}

# Statistical county subdivisions -- census county divisions and unorganized
# territories. They are analytical areas, not places anybody addresses mail to,
# and including them adds name collisions without adding reach.
STATISTICAL_CLASSES = {"Z5", "Z7"}

# NOTE: foundation_countries already exists and holds international giving.
# One letter apart, and its indexes are called idx_fc_*, which these must not
# collide with. Read the name twice before touching either.
SCHEMA = """
DROP TABLE IF EXISTS foundation_counties;
CREATE TABLE foundation_counties (
    ein        TEXT NOT NULL,
    state      TEXT NOT NULL,
    county     TEXT NOT NULL,
    dollars    INTEGER NOT NULL,
    grants     INTEGER NOT NULL,
    PRIMARY KEY (ein, state, county)
);
"""
INDEXES = """
DROP INDEX IF EXISTS idx_county_ein;
DROP INDEX IF EXISTS idx_county_lookup;
CREATE INDEX idx_county_ein ON foundation_counties(ein, dollars DESC);
CREATE INDEX idx_county_lookup
    ON foundation_counties(state, county, dollars DESC);
"""

# Where a recipient IS, as opposed to where a funder gives. The recipients
# table carries no address at all -- location exists only per grant, on
# grants.recipient_city/state -- so it has to be derived.
#
# One row per recipient, not one per place. An organisation has an address;
# the several cities that show up for 12% of them are the same org written
# from different filings, or an org that moved, not an org in two places. The
# dominant place by dollars wins, and place_count records how many were seen
# so a caller can tell a clean match from a contested one.
RECIPIENT_SCHEMA = """
DROP TABLE IF EXISTS recipient_counties;
CREATE TABLE recipient_counties (
    entity_id   TEXT PRIMARY KEY,
    state       TEXT NOT NULL,
    county      TEXT NOT NULL,
    city        TEXT NOT NULL,
    dollars     INTEGER NOT NULL,
    place_count INTEGER NOT NULL
);
"""
RECIPIENT_INDEXES = """
DROP INDEX IF EXISTS idx_rc_lookup;
DROP INDEX IF EXISTS idx_rc_state;
CREATE INDEX idx_rc_lookup ON recipient_counties(state, county);
CREATE INDEX idx_rc_state ON recipient_counties(state);
"""


def log(msg: str) -> None:
    print(f"[geo-index] {msg}", flush=True)


def fetch(name: str, url: str) -> Path:
    """Cached under data/census, so a rebuild does not need the network."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if path.exists() and path.stat().st_size > 0:
        return path
    log(f"downloading {name}")
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            path.write_bytes(response.read())
    except urllib.error.URLError as exc:
        # urllib uses its own CA bundle, which on macOS is often unpopulated.
        # curl works where this does not, so say so rather than printing a
        # TLS traceback that reads like the file is missing.
        raise SystemExit(
            f"could not download {name}: {exc}\n"
            f"Fetch it by hand and re-run:\n"
            f"  mkdir -p {CACHE}\n"
            f"  curl -o {CACHE / name} {url}") from exc
    return path


def primary_county(place: str, counties: str | None) -> str | None:
    """One county for a place, even when it straddles several.

    1,304 places span more than one, and the file separates them with "~~~"
    -- not a comma, which is what an earlier version of this split on. That
    produced county names like "Bronx County~~~Kings County~~~New York
    County" on 101,167 rows carrying $37.55B.

    The list is alphabetical, not ordered by size, so taking the first is
    arbitrary: it would file all of New York City under the Bronx. Where one
    of the candidates shares the place's own name it is preferred -- New York
    city to New York County, Kansas City to no match and so onto the fallback
    -- and otherwise the first is taken and the limitation stands.
    """
    parts = [c.strip() for c in re.split(r"~~~|,", counties or "") if c.strip()]
    if not parts:
        return None
    key = place_key(place)
    for candidate in parts:
        if key and key in place_key(candidate):
            return candidate
    return parts[0]


def build_crosswalk() -> dict[tuple[str, str], str]:
    """(state, normalised place) -> county name."""
    votes: dict[tuple[str, str], collections.Counter] = \
        collections.defaultdict(collections.Counter)

    with fetch("place2020.txt", SOURCES["place2020.txt"]).open(
            encoding="latin-1") as fh:
        for row in csv.DictReader(fh, delimiter="|"):
            county = primary_county(row["PLACENAME"], row["COUNTIES"])
            if not county:
                continue
            name = row["PLACENAME"]
            key = place_key(name)
            if not key:
                continue
            votes[(row["STATE"], key)][county] += 8
            alias = place_alias(name)
            if alias:
                votes[(row["STATE"], alias)][county] += 2

    with fetch("cousub2020.txt", SOURCES["cousub2020.txt"]).open(
            encoding="latin-1") as fh:
        for row in csv.DictReader(fh, delimiter="|"):
            county = (row["COUNTYNAME"] or "").strip()
            if not county or row["CLASSFP"] in STATISTICAL_CLASSES:
                continue
            name = row["COUSUBNAME"]
            key = place_key(name)
            if not key:
                continue
            votes[(row["STATE"], key)][county] += 4
            alias = place_alias(name)
            if alias:
                votes[(row["STATE"], alias)][county] += 1

    return {k: v.most_common(1)[0][0] for k, v in votes.items()}


def county_of(crosswalk, city: str | None, state: str | None) -> str | None:
    if not city or not state or is_placeholder(city):
        return None
    for key in place_keys(city):
        found = crosswalk.get((state.upper(), key))
        if found:
            return found
    return None


def build_recipient_counties(conn, crosswalk) -> None:
    """Give every recipient one location, derived from its own grants."""
    conn.executescript(RECIPIENT_SCHEMA)

    rows = conn.execute("""
        SELECT entity_id, recipient_state, recipient_city, SUM(amount) dollars
        FROM grants
        WHERE entity_id IS NOT NULL
          AND COALESCE(recipient_state,'') != ''
          AND COALESCE(recipient_city,'') != ''
        GROUP BY entity_id, recipient_state, recipient_city
        ORDER BY entity_id
    """)

    # best[entity_id] = (dollars, state, county, city); seen counts the
    # distinct places, including ones no county could be found for -- a
    # recipient split between two cities is contested whether or not both
    # cities resolved.
    best: dict[str, tuple[int, str, str, str]] = {}
    seen: collections.Counter = collections.Counter()
    while True:
        chunk = rows.fetchmany(50_000)
        if not chunk:
            break
        for entity_id, state, city, dollars in chunk:
            seen[entity_id] += 1
            county = county_of(crosswalk, city, state)
            if county is None:
                continue
            amount = int(dollars or 0)
            current = best.get(entity_id)
            if current is None or amount > current[0]:
                best[entity_id] = (amount, state.upper(), county, city)

    conn.executemany(
        "INSERT INTO recipient_counties"
        "(entity_id, state, county, city, dollars, place_count) "
        "VALUES (?,?,?,?,?,?)",
        [(eid, s, c, city, d, seen[eid])
         for eid, (d, s, c, city) in best.items()])
    conn.executescript(RECIPIENT_INDEXES)
    conn.commit()

    total = conn.execute(
        "SELECT COUNT(*) FROM recipients WHERE total_received > 0").fetchone()[0]
    contested = sum(1 for eid in best if seen[eid] > 1)
    log(f"recipients placed in a county: {len(best):,} of {total:,} "
        f"({100*len(best)/total:.1f}%); {contested:,} had more than one "
        f"place on file and took the one with the most dollars")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    db = Path(args.db)
    if not db.exists():
        log(f"ERROR: no such database: {db}")
        return 1

    started = time.monotonic()
    crosswalk = build_crosswalk()
    log(f"crosswalk: {len(crosswalk):,} (state, place) entries")

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

    rows = conn.execute("""
        SELECT funder_ein, recipient_state, recipient_city,
               SUM(amount) AS dollars, COUNT(*) AS grants
        FROM grants
        WHERE COALESCE(recipient_state,'') != ''
          AND COALESCE(recipient_city,'') != ''
        GROUP BY funder_ein, recipient_state, recipient_city
    """)

    agg: dict[tuple[str, str, str], list[int]] = collections.defaultdict(
        lambda: [0, 0])
    placed = unplaced = 0
    while True:
        chunk = rows.fetchmany(50_000)
        if not chunk:
            break
        for ein, state, city, dollars, grants in chunk:
            county = county_of(crosswalk, city, state)
            if county is None:
                unplaced += dollars or 0
                continue
            placed += dollars or 0
            slot = agg[(ein, state.upper(), county)]
            slot[0] += dollars or 0
            slot[1] += grants or 0

    conn.executemany(
        "INSERT INTO foundation_counties(ein, state, county, dollars, grants) "
        "VALUES (?,?,?,?,?)",
        [(e, s, c, int(d), int(g)) for (e, s, c), (d, g) in agg.items()])
    conn.executescript(INDEXES)
    conn.commit()

    total = placed + unplaced
    log(f"rolled up {len(agg):,} (funder, county) rows")
    log(f"placed ${placed/1e9:.2f}B of ${total/1e9:.2f}B "
        f"({100*placed/total:.1f}%); ${unplaced/1e9:.2f}B had no usable city")
    log(f"distinct counties: "
        f"{len({(s, c) for _, s, c in agg}):,}")

    build_recipient_counties(conn, crosswalk)

    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.close()
    log(f"done in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
