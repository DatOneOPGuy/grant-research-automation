"""Task 5 — downstream impact of strict identity on verdicts (PROJECTION).

Proxy method, clearly labeled: the v2 evidence ledger does not exist yet, so
"confirmed Christian" is approximated with the legacy deterministic name rules
(src.classifier) applied to BMF canonical names of *resolved* entities only.
Unresolved/collision dollars are unclassifiable by construction. Read-only.
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classifier import classify  # noqa: E402

RUN = "identity-20260714T014241Z"
STRONG_DOLLARS = 100_000
STRONG_ENTITIES = 3


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def main() -> None:
    conn = sqlite3.connect(
        f"file:{Path('data/grants_v2.db').resolve()}?mode=ro", uri=True, timeout=60)
    log("classifying resolved entity names with legacy rules…")
    verdicts: dict[str, str | None] = {}
    for entity_id, name in conn.execute(
        "SELECT entity_id, canonical_name FROM recipient_entities "
        "WHERE run_id=? AND identity_status='matched_bmf'", (RUN,)):
        verdicts[entity_id] = classify(name or "")
    christian = {e for e, v in verdicts.items() if v == "christian"}
    nonchristian = {e for e, v in verdicts.items() if v == "nonchristian"}
    log(f"resolved entities: {len(verdicts):,} | christian-rule {len(christian):,} "
        f"| nonchristian-rule {len(nonchristian):,}")

    log("aggregating per-foundation paid dollars by bucket (TY2023-24)…")
    per_foundation: dict[str, dict[str, float | set]] = {}
    buckets = {"christian": 0.0, "nonchristian": 0.0, "unclassified": 0.0}
    cursor = conn.execute("""
        SELECT t.ein, em.entity_id, e.identity_status, g.signed_amount
        FROM grant_norm g
        JOIN grant_transactions t ON t.grant_id=g.grant_id
        JOIN recipient_entity_mentions em
          ON em.run_id=g.run_id AND em.mention_id=g.mention_id
        JOIN recipient_entities e
          ON e.run_id=em.run_id AND e.entity_id=em.entity_id
        WHERE g.run_id=? AND g.tax_year IN (2023, 2024)
    """, (RUN,))
    rows = 0
    while True:
        chunk = cursor.fetchmany(500_000)
        if not chunk:
            break
        for funder, entity_id, status, amount in chunk:
            record = per_foundation.setdefault(
                funder, {"christian": 0.0, "entities": set(), "total": 0.0})
            record["total"] += amount
            if status == "matched_bmf" and entity_id in christian:
                buckets["christian"] += amount
                record["christian"] += amount
                record["entities"].add(entity_id)
            elif status == "matched_bmf" and entity_id in nonchristian:
                buckets["nonchristian"] += amount
            else:
                buckets["unclassified"] += amount
        rows += len(chunk)
        log(f"  {rows:,} grant rows processed")

    strong = [
        (ein, record) for ein, record in per_foundation.items()
        if record["christian"] >= STRONG_DOLLARS
        and len(record["entities"]) >= STRONG_ENTITIES
    ]
    some = sum(1 for record in per_foundation.values() if record["christian"] > 0)
    total = sum(v for v in buckets.values())
    print("\n## Task 5 — Downstream impact (rule-proxy projection, TY2023-24)\n")
    print("Method: legacy deterministic name rules on resolved BMF canonical "
          "names only. The real evidence ledger (NTEE, church codes, 990 "
          "mission text) will move these numbers — treat as a floor.\n")
    print("| Bucket (TY23-24 paid $) | $ | share |")
    print("|---|---|---|")
    for k, v in buckets.items():
        print(f"| {k} | ${v/1e9:.2f}B | {100*v/total:.1f}% |")
    print(f"\nFoundations with any rule-confirmed Christian paid dollars: {some:,}")
    print(f"**Strong-verdict foundations (>=${STRONG_DOLLARS:,} AND "
          f">={STRONG_ENTITIES} distinct confirmed entities): {len(strong):,}** "
          "(v1 claimed 8,236)")
    log("done")


if __name__ == "__main__":
    main()
