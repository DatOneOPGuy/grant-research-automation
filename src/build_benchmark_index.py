"""Build the international-benchmark index.

    python3 -m src.build_benchmark_index
    python3 -m src.build_benchmark_index --review     # audit what matched

Answers "which foundations fund the major international ministries", which is
the question the International filter cannot answer -- that one keys off a
foreign mailing address, and these organisations are all headquartered in the
US. See src/international_orgs.py for the curated list and why it is curated.

Two tables:

  benchmark_orgs   one row per ministry, with what it resolved to
  benchmark_hits   (funder_ein, slug) -- who funded whom, and how much

A foundation's priority tier is how many DISTINCT ministries it funded. One
is a data point; four is a foundation with a deliberate international
programme. That count is what the filter sorts and tiers on.

--review writes benchmark_review.csv: every recipient name each entry
claimed, with its dollars. Read it when adding an organisation. A pattern
that over-matches does not fail loudly -- it quietly labels the wrong
foundations as international prospects, which is worse than missing them.
"""

from __future__ import annotations

import argparse
import collections
import csv
import re
import sqlite3
import sys
import time
from pathlib import Path

from src.international_orgs import (
    CATEGORIES,
    NON_INTERNATIONAL_CATEGORIES,
    ORGS,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "explorer_v5.db"
REVIEW_CSV = ROOT / "data" / "benchmark_review.csv"

SCHEMA = """
DROP TABLE IF EXISTS benchmark_orgs;
DROP TABLE IF EXISTS benchmark_hits;
CREATE TABLE benchmark_orgs (
    slug        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    name_count  INTEGER NOT NULL,   -- distinct recipient rows it matched
    dollars     INTEGER NOT NULL,   -- total received across those rows
    funders     INTEGER NOT NULL
);
CREATE TABLE benchmark_hits (
    ein     TEXT NOT NULL,
    slug    TEXT NOT NULL,
    dollars INTEGER NOT NULL,
    grants  INTEGER NOT NULL,
    PRIMARY KEY (ein, slug)
);
"""
INDEXES = """
DROP INDEX IF EXISTS idx_bench_ein;
DROP INDEX IF EXISTS idx_bench_slug;
CREATE INDEX idx_bench_ein ON benchmark_hits(ein);
CREATE INDEX idx_bench_slug ON benchmark_hits(slug, dollars DESC);
"""


def log(msg: str) -> None:
    print(f"[benchmark] {msg}", flush=True)


def compile_org(org):
    """Patterns are matched against a squashed name.

    Punctuation and spacing in 990-PF grant schedules is arbitrary --
    "Samaritan's Purse", "SAMARITANS PURSE", "Samaritan  Purse" are all the
    same organisation -- so both sides are normalised before matching rather
    than trying to write patterns that anticipate every spelling.
    """
    pats = [re.compile(p, re.IGNORECASE) for p in org.patterns]
    excl = [re.compile(p, re.IGNORECASE) for p in org.exclude]
    return pats, excl, set(org.eins)


_PUNCT = re.compile(r"[^a-z0-9]+")


def squash(name: str | None) -> str:
    return _PUNCT.sub(" ", (name or "").lower()).strip()


def resolve(conn) -> dict[str, list[tuple]]:
    """slug -> [(entity_id, name, ein, total_received), ...]"""
    compiled = {o.slug: compile_org(o) for o in ORGS}
    matches: dict[str, list[tuple]] = collections.defaultdict(list)

    rows = conn.execute("""
        SELECT entity_id, name, ein, total_received
        FROM recipients WHERE total_received > 0""")
    while True:
        chunk = rows.fetchmany(50_000)
        if not chunk:
            break
        for entity_id, name, ein, total in chunk:
            flat = squash(name)
            for org in ORGS:
                pats, excl, eins = compiled[org.slug]
                by_ein = bool(ein) and ein in eins
                # An explicit EIN is a stronger statement than a name
                # pattern, so it overrides the exclusions -- those exist to
                # fix over-broad patterns, not to veto a stated identity.
                if not by_ein:
                    if not any(p.search(flat) for p in pats):
                        continue
                    if any(p.search(flat) for p in excl):
                        continue
                matches[org.slug].append((entity_id, name, ein, total or 0))
    return matches


def write_review(conn, matches) -> None:
    REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["slug", "ministry", "category", "matched_name", "ein",
                    "total_received", "funders"])
        for org in ORGS:
            rows = sorted(matches.get(org.slug, []), key=lambda r: -r[3])
            if not rows:
                w.writerow([org.slug, org.name, org.category,
                            "*** NO MATCH ***", "", 0, 0])
                continue
            for entity_id, name, ein, total in rows:
                funders = conn.execute(
                    "SELECT COUNT(DISTINCT funder_ein) FROM grants "
                    "WHERE entity_id = ?", (entity_id,)).fetchone()[0]
                w.writerow([org.slug, org.name, org.category, name,
                            ein or "", int(total), funders])
    log(f"review written to {REVIEW_CSV}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--review", action="store_true",
                        help="also dump benchmark_review.csv")
    args = parser.parse_args()

    validate()
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

    matches = resolve(conn)
    empty = [o.slug for o in ORGS if not matches.get(o.slug)]
    if empty:
        # Not fatal: a ministry may genuinely take no 990-PF money in the
        # window. But it is nearly always a typo in a pattern, so say so.
        log(f"WARNING: matched nothing: {', '.join(empty)}")

    conn.executescript(SCHEMA)
    for org in ORGS:
        rows = matches.get(org.slug, [])
        ids = [r[0] for r in rows]
        funders = 0
        if ids:
            marks = ",".join("?" for _ in ids)
            funders = conn.execute(
                "SELECT COUNT(DISTINCT funder_ein) FROM grants "  # noqa: S608
                f"WHERE entity_id IN ({marks})", ids).fetchone()[0]
        conn.execute(
            "INSERT INTO benchmark_orgs"
            "(slug, name, category, name_count, dollars, funders) "
            "VALUES (?,?,?,?,?,?)",
            (org.slug, org.name, org.category, len(rows),
             int(sum(r[3] for r in rows)), funders))

        if not ids:
            continue
        marks = ",".join("?" for _ in ids)
        hits = conn.execute(
            "SELECT funder_ein, SUM(amount), COUNT(*) FROM grants "  # noqa: S608
            f"WHERE entity_id IN ({marks}) GROUP BY funder_ein", ids
        ).fetchall()
        conn.executemany(
            "INSERT INTO benchmark_hits(ein, slug, dollars, grants) "
            "VALUES (?,?,?,?)",
            [(ein, org.slug, int(d or 0), n) for ein, d, n in hits])

    conn.executescript(INDEXES)
    conn.commit()

    total_funders = conn.execute(
        "SELECT COUNT(DISTINCT ein) FROM benchmark_hits").fetchone()[0]
    log(f"{len(ORGS)} ministries in {len(CATEGORIES)} categories")
    log(f"{total_funders:,} foundations fund at least one")
    excluded = ",".join(f"'{c}'" for c in NON_INTERNATIONAL_CATEGORIES)
    log("by number of distinct INTERNATIONAL ministries funded "
        f"(excluding categories: {excluded}):")
    for tier, count in conn.execute(f"""
            SELECT n, COUNT(*) FROM (
              SELECT bh.ein, COUNT(DISTINCT bh.slug) n
              FROM benchmark_hits bh
              JOIN benchmark_orgs bo ON bo.slug = bh.slug
              WHERE bo.category NOT IN ({excluded})
              GROUP BY bh.ein) GROUP BY n ORDER BY n DESC LIMIT 6"""):  # noqa: S608
        log(f"    {tier:>2}+ ministries: {count:,} foundations")

    if args.review:
        write_review(conn, matches)

    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.close()
    log(f"done in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
