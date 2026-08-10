"""Supersede name-rule evidence invalidated by the v3 classifier fixes.

The evidence ledger is append-only, so a corrected rule cannot delete what an
earlier version wrote. This pass re-runs the rule over every entity that
already carries `recipient-name-rule-v2` evidence, and writes a v3 row wherever
the verdict changed:

  - the rule now yields a different label  -> write that label
  - the rule now yields nothing at all     -> write `unknown`, which shadows v2
    via newest_rule_only() and is then dropped by eligible_evidence(), leaving
    the entity unclassified rather than wrongly Christian

Entities whose verdict is unchanged get no new row: v2 remains the newest
version for them and stays authoritative. Nothing is mutated or deleted.

Writes data/grants_v2.db. Never touches data/grants.db.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

from src.classification_seed_v2 import rule_label
from src.classification_store import (
    Evidence,
    append_evidence,
    build_release,
    create_classification_schema,
    create_run,
)

DB = Path("data/grants_v2.db")
RULE_ID = "recipient-name-rule-v3"   # default; override with --rule-version
CHUNK = 5_000


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def superseded_candidates(conn: sqlite3.Connection, identity_run: str,
                          rule_id: str):
    """Entities whose CURRENTLY-WINNING rule label may now be wrong.

    Compares against the newest rule version already on the ledger, not against
    v2, so successive correction passes chain correctly: a v4 pass must
    supersede whatever v3 concluded, not re-litigate v2.
    """
    return conn.execute(
        """
        WITH newest AS (
          SELECT entity_id, MAX(source_rule_id) AS top_rule
          FROM classification_evidence
          WHERE evidence_method = 'rule' AND source_rule_id < ?
          GROUP BY entity_id
        )
        SELECT e.entity_id, e.canonical_name, e.identity_status,
               MAX(ce.classification) AS old_label
        FROM recipient_entities e
        JOIN newest n ON n.entity_id = e.entity_id
        JOIN classification_evidence ce
          ON ce.entity_id = e.entity_id
         AND ce.source_rule_id = n.top_rule
        WHERE e.run_id = ?
        GROUP BY e.entity_id
        """,
        (rule_id, identity_run),
    ).fetchall()


def main() -> None:
    ap = argparse.ArgumentParser(prog="python3 -m src.reclassify_rule_v3",
                                 description=__doc__)
    ap.add_argument("--identity-run", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rule-version", default=RULE_ID)
    args = ap.parse_args()
    rule_id = args.rule_version

    started = time.monotonic()
    conn = sqlite3.connect(DB, timeout=60)
    create_classification_schema(conn)
    rows = superseded_candidates(conn, args.identity_run, rule_id)
    log(f"entities carrying prior rule evidence: {len(rows):,}")

    changed = []
    for entity_id, name, identity_status, old_label in rows:
        new_label = rule_label(name)
        if new_label != old_label:
            changed.append((entity_id, name, identity_status,
                            old_label, new_label))
    retracted = sum(1 for c in changed if c[4] is None)
    relabelled = len(changed) - retracted
    log(f"verdict changed: {len(changed):,} "
        f"(retracted to unknown: {retracted:,}, relabelled: {relabelled:,})")
    if args.dry_run:
        log("dry run - nothing written")
        conn.close()
        return
    if not changed:
        conn.close()
        return

    run_id = create_run(conn, args.identity_run, "rule",
                        engine_name=rule_id,
                        config={"fix": "rx-boundary-guard+place-literals"})
    log(f"classification run {run_id}")
    for index, (entity_id, name, identity_status, old_label, new_label) in \
            enumerate(changed, 1):
        append_evidence(
            conn, run_id, args.identity_run,
            Evidence(
                entity_id,
                new_label or "unknown",
                0.90,
                "rule",
                reason=(f"name rule {rule_id} supersedes prior version: "
                        + ("no religious signal survives the boundary and "
                           "place-name guards" if new_label is None
                           else f"reclassified {old_label} -> {new_label}")),
                source_rule_id=rule_id,
                source_record={"name": name,
                               "identity_status": identity_status,
                               "superseded_label": old_label},
            ),
        )
        if index % CHUNK == 0:
            conn.commit()
            log(f"  written {index:,}/{len(changed):,}")
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
