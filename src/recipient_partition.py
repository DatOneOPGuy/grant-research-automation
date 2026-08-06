"""Partition unresolved recipients: structurally unresolvable vs revisitable.

Recipient-side bookkeeping only. Nothing here changes a foundation's totals,
coverage, or verdicts -- the coverage denominator already handles unresolvable
dollars correctly at the foundation level. The point is to let future identity
passes skip names that cannot be resolved by anyone from public data, without
burying a high-dollar recipient that a human could resolve.

Disposition is assigned conservatively: an entity is parked as
`unresolvable_structural` only when EVERY revisit signal is absent. Any single
signal sends it to `unresolved_revisitable`, because revisiting a name twice is
cheap and burying a resolvable high-dollar recipient is not.

Revisit signals (any one is sufficient):
  collision        -- identity matched several EINs; candidates already exist,
                      it is disambiguation work, not missing information
  alias_queue      -- on the curated alias tranche-2 list (Gates is rank 1)
  dollars >= $10k  -- volume warrants human curation. The tail below this line
                      is 557,916 entities holding $0.89B, 1.8% of unresolved
                      dollars, so the threshold parks ~70% of the entities
                      while risking under 2% of the money
  bmf_exact        -- normalized name matches a BMF organization exactly
  bmf_prefix       -- normalized name is a prefix of exactly one BMF
                      organization, which is the IRS-truncation shape
                      ("national philanthropic tr")
  mission_text     -- a 990 is already on disk, so it is trivially revisitable

Writes data/grants_v2.db (v2 substrate). Never touches data/grants.db.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from src.identity_normalize import normalize_identity_name

PIPELINE_DB = Path("data/grants_v2.db")
BMF_DB = Path("data/bmf_registry.db")
EXPLORER_DB = Path("data/explorer_v5.db")
ALIAS_QUEUE = Path("data/alias_queue.csv")
CURATION_FLOOR = 10_000
CHUNK = 20_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS recipient_dispositions (
    identity_run_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    disposition TEXT NOT NULL
        CHECK (disposition IN ('unresolvable_structural',
                               'unresolved_revisitable')),
    reason TEXT NOT NULL,
    dollars INTEGER NOT NULL DEFAULT 0,
    created_at_utc TEXT NOT NULL,
    PRIMARY KEY (identity_run_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_rd_disposition
    ON recipient_dispositions(identity_run_id, disposition);
"""


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def load_alias_norms() -> set[str]:
    if not ALIAS_QUEUE.exists():
        log(f"WARNING: {ALIAS_QUEUE} missing; alias signal unavailable")
        return set()
    with ALIAS_QUEUE.open(newline="") as handle:
        norms = {
            (row.get("name_norm") or "").strip()
            for row in csv.DictReader(handle)
        }
    norms.discard("")
    log(f"alias queue: {len(norms):,} curated names")
    return norms


def load_bmf_index() -> tuple[set[str], list[str]]:
    """Normalized BMF names: a set for exact hits, sorted for prefix hits."""
    conn = sqlite3.connect(f"file:{BMF_DB.resolve()}?mode=ro", uri=True)
    try:
        names = {
            normalize_identity_name(row[0])
            for row in conn.execute(
                "SELECT organization_name FROM bmf_organizations")
        }
    finally:
        conn.close()
    names.discard("")
    log(f"BMF index: {len(names):,} distinct normalized names")
    return names, sorted(names)


def unique_prefix_match(sorted_names: list[str], needle: str) -> bool:
    """True when `needle` prefixes exactly one BMF name (IRS truncation)."""
    if len(needle) < 8:
        return False
    start = bisect.bisect_left(sorted_names, needle)
    if start >= len(sorted_names) or not sorted_names[start].startswith(needle):
        return False
    second = start + 1
    return not (second < len(sorted_names)
                and sorted_names[second].startswith(needle))


def classify_rows(rows, alias_norms, bmf_exact, bmf_sorted):
    """Yield (entity_id, disposition, reason, dollars) for each candidate."""
    for entity_id, name, status, dollars in rows:
        dollars = dollars or 0
        reasons = []
        if status == "collision":
            reasons.append("collision:candidate_eins_exist")
        norm = normalize_identity_name(name)
        if norm and norm in alias_norms:
            reasons.append("alias_queue")
        if dollars >= CURATION_FLOOR:
            reasons.append(f"dollars>={CURATION_FLOOR}")
        if norm and norm in bmf_exact:
            reasons.append("bmf_exact_name")
        elif norm and unique_prefix_match(bmf_sorted, norm):
            reasons.append("bmf_unique_prefix")
        if reasons:
            yield entity_id, "unresolved_revisitable", ",".join(reasons), dollars
        else:
            yield (entity_id, "unresolvable_structural",
                   "no_bmf_candidate,no_alias,below_curation_floor", dollars)


def candidate_rows(explorer: sqlite3.Connection):
    return explorer.execute("""
        SELECT entity_id, name, identity_status, total_received
        FROM recipients
        WHERE identity_status IN ('unresolved', 'collision')
          AND COALESCE(mission_text, '') = ''
    """)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python3 -m src.recipient_partition", description=__doc__)
    parser.add_argument("--identity-run", required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="report the split without writing")
    args = parser.parse_args()

    started = time.monotonic()
    alias_norms = load_alias_norms()
    bmf_exact, bmf_sorted = load_bmf_index()

    explorer = sqlite3.connect(f"file:{EXPLORER_DB.resolve()}?mode=ro", uri=True)
    pipeline = None
    if not args.dry_run:
        pipeline = sqlite3.connect(PIPELINE_DB)
        pipeline.executescript(SCHEMA)
        pipeline.execute(
            "DELETE FROM recipient_dispositions WHERE identity_run_id=?",
            (args.identity_run,))
        pipeline.commit()

    stamp = datetime.now(UTC).isoformat()
    tally: dict[str, int] = {}
    money: dict[str, int] = {}
    batch, total = [], 0
    try:
        for entity_id, disposition, reason, dollars in classify_rows(
                candidate_rows(explorer), alias_norms, bmf_exact, bmf_sorted):
            tally[disposition] = tally.get(disposition, 0) + 1
            money[disposition] = money.get(disposition, 0) + dollars
            total += 1
            if pipeline is not None:
                batch.append((args.identity_run, entity_id, disposition,
                              reason, dollars, stamp))
                if len(batch) >= CHUNK:
                    pipeline.executemany(
                        "INSERT OR REPLACE INTO recipient_dispositions VALUES "
                        "(?,?,?,?,?,?)", batch)
                    pipeline.commit()
                    batch.clear()
                    log(f"  written {total:,}…")
        if pipeline is not None and batch:
            pipeline.executemany(
                "INSERT OR REPLACE INTO recipient_dispositions VALUES "
                "(?,?,?,?,?,?)", batch)
            pipeline.commit()
    finally:
        explorer.close()
        if pipeline is not None:
            # Checkpoint before closing: a lingering WAL is how this project
            # previously corrupted a multi-GB database during a file move.
            pipeline.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            pipeline.close()

    log(f"candidates: {total:,}")
    for disposition in sorted(tally):
        log(f"  {disposition}: {tally[disposition]:,} "
            f"(${money[disposition] / 1e9:,.2f}B)")
    log(f"done in {time.monotonic() - started:,.0f}s"
        f"{' (dry run, nothing written)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
