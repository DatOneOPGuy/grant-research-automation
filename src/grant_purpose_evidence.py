"""Phase 2: write grant-purpose evidence to the classification ledger.

Grant purpose describes ONE GRANT, not an organisation's identity, so it enters
the ledger deliberately weakened:

  * method `grant_purpose` at priority 40 -- below llm/mission (50) and every
    deterministic tier, so it can fill a gap or corroborate but can never
    override mission text, NTEE, church code, a group ruling or a name rule.

  * the anti-over-claim gate: evidence is emitted only when the recipient's
    religious-purpose grants are a MAJORITY of its dollars, or come from TWO
    OR MORE independent funders. A single restricted gift cannot reclassify a
    whole organisation -- this is what stops Duke University (4% of dollars,
    one Divinity School initiative) being labelled Christian.

  * contradictions never auto-resolve. Where a recipient already carries a
    non-Christian verdict, nothing is written; the case stays in the Phase 1
    review queue for a human.

Only `christian_unspecified` is ever asserted. The purpose text says the money
was for Christian work; it rarely identifies a denomination, and guessing one
would be imputation.

Writes data/grants_v2.db. Never touches data/grants.db.
"""

from __future__ import annotations

import argparse
import collections
import sqlite3
import sys
import time
from pathlib import Path

from src.classification_store import (
    Evidence,
    append_evidence,
    build_release,
    create_classification_schema,
    create_run,
)
from src.grant_purpose_signal import christian_signal, quote

EXPLORER = Path("data/explorer_v5.db")
DB = Path("data/grants_v2.db")
METHOD = "grant_purpose"
CONFIDENCE = 0.75
CHRISTIAN = ("evangelical_protestant", "catholic", "orthodox_christian",
             "christian_unspecified")
CHUNK = 2_000


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def gather() -> dict:
    conn = sqlite3.connect(f"file:{EXPLORER.resolve()}?mode=ro", uri=True)
    per = collections.defaultdict(lambda: {
        "dollars": 0, "grants": 0, "funders": set(), "quotes": [],
        "tradition": None, "total": 0, "name": None})
    scanned = 0
    for entity_id, amount, purpose, funder, tradition, total, name in \
            conn.execute("""
                SELECT g.entity_id, g.amount, g.purpose, g.funder_ein,
                       r.tradition, r.total_received, r.name
                FROM grants g
                LEFT JOIN recipients r ON r.entity_id = g.entity_id"""):
        scanned += 1
        if scanned % 1_000_000 == 0:
            log(f"  scanned {scanned:,}")
        if not christian_signal(purpose):
            continue
        row = per[entity_id]
        row["dollars"] += amount or 0
        row["grants"] += 1
        row["funders"].add(funder)
        row["tradition"] = tradition
        row["total"] = total or 0
        row["name"] = name
        if len(row["quotes"]) < 3:
            row["quotes"].append((funder, quote(purpose)))
    conn.close()
    log(f"  scanned {scanned:,} grants; recipients with a signal: {len(per):,}")
    return per


def passes_gate(row: dict) -> bool:
    """The hard gate. Two or more independent funders, or a majority of the
    recipient's dollars. Anything else is a review item, not evidence."""
    if len(row["funders"]) >= 2:
        return True
    return row["total"] > 0 and row["dollars"] * 2 > row["total"]


def main() -> None:
    ap = argparse.ArgumentParser(prog="python3 -m src.grant_purpose_evidence",
                                 description=__doc__)
    ap.add_argument("--identity-run", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    started = time.monotonic()
    per = gather()

    emit, held = [], collections.Counter()
    for entity_id, row in per.items():
        if row["tradition"] in CHRISTIAN:
            held["already christian (corroboration only, no row needed)"] += 1
            continue
        if row["tradition"] is not None:
            held["contradiction -> review queue, never auto-resolved"] += 1
            continue
        if not passes_gate(row):
            held["failed anti-over-claim gate (single funder, minority)"] += 1
            continue
        emit.append((entity_id, row))

    log(f"eligible to write: {len(emit):,} recipients "
        f"(${sum(r['dollars'] for _, r in emit) / 1e6:,.1f}M)")
    for reason, count in held.most_common():
        log(f"  held: {reason}: {count:,}")
    if args.dry_run:
        log("dry run - nothing written")
        return

    conn = sqlite3.connect(DB, timeout=60)
    create_classification_schema(conn)
    run_id = create_run(conn, args.identity_run, METHOD,
                        engine_name="grant-purpose-v1",
                        config={"confidence": CONFIDENCE,
                                "gate": "2+ funders or majority of dollars"})
    log(f"classification run {run_id}")
    for index, (entity_id, row) in enumerate(emit, 1):
        funder, text = row["quotes"][0]
        append_evidence(
            conn, run_id, args.identity_run,
            Evidence(
                entity_id,
                "christian_unspecified",
                CONFIDENCE,
                METHOD,
                reason=(f'funder {funder} states the grant purpose as '
                        f'"{text}"'),
                source_rule_id="grant-purpose-v1",
                source_record={
                    "religious_grants": row["grants"],
                    "religious_dollars": row["dollars"],
                    "distinct_funders": sorted(row["funders"])[:10],
                    "recipient_total_dollars": row["total"],
                    "quotes": [{"funder_ein": f, "purpose": q}
                               for f, q in row["quotes"]],
                },
            ),
        )
        if index % CHUNK == 0:
            conn.commit()
            log(f"  written {index:,}/{len(emit):,}")
    conn.commit()
    log("building classification release…")
    release_id = build_release(conn, args.identity_run)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    log(f"release {release_id}")
    log(f"done in {time.monotonic() - started:,.0f}s")
    print(release_id)


if __name__ == "__main__":
    main()
