"""Deterministic non-organization dispositions, applied before BMF matching.

A mention with a disposition is not an identification failure — it is a
placeholder, a natural person, a government body, or a foreign organization,
none of which can or should resolve against the BMF. Dispositions are
assigned by conservative name patterns plus the filer's own
recipient_foundation_status, and every rule is visible here for audit.
"""

from __future__ import annotations

import re
import sqlite3
import sys
import time

# Filing artifacts and aggregates: "ATCH 4", "See Statement 17",
# "VARIOUS NEEDY PATIENTS", "Donation of Inventories", bare "GRANTS".
UNATTRIBUTABLE = re.compile(
    r"^(atch|see |statement|schedule|attachment|exhibit|various|misc)\b"
    r"|^(n ?a|none|not applicable|no grants?|grants?|donations?( us)?)$"
    r"|\b(various|see attached|see attachment|see statement|see schedule|"
    r"list available|available upon request|per attached|attached list|"
    r"hipp?aa?|individual patient|patient programs?|eligible patients?|"
    r"needy patients?|various individuals?|anonymous|sundry|"
    r"scholarship recipients?|grant recipients?|donation of inventor)\b")

GOVERNMENT = re.compile(
    r"^(city|town|county|state|village|borough|township|commonwealth|"
    r"government) of\b"
    r"|\b(school district|dept of|department of) \b"
    r"|^(us|united states) (government|treasury|dept|department)\b")


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def bucket_case(column: str) -> str:
    """Normalize the filer's free-text recipient_foundation_status."""
    return f"""CASE
      WHEN {column} IS NULL OR TRIM({column})='' THEN 'blank'
      WHEN UPPER({column}) LIKE 'PC%' OR UPPER({column}) LIKE 'PUBLIC%'
        OR UPPER({column}) LIKE '509(A)%' OR UPPER({column}) LIKE '170(B)%'
        OR UPPER({column}) LIKE '501(C)(3)%' OR UPPER({column}) LIKE 'EXEMPT%'
        OR UPPER({column}) LIKE 'CHARIT%' THEN 'PC'
      WHEN UPPER({column}) LIKE 'PF%' OR UPPER({column}) LIKE 'PRIVATE%'
        OR UPPER({column}) LIKE 'POF%' THEN 'PF'
      WHEN UPPER({column}) LIKE 'NC%' OR UPPER({column}) LIKE 'NON%' THEN 'NC'
      WHEN UPPER({column}) LIKE 'GOV%' THEN 'GOV'
      WHEN UPPER({column}) IN ('I', 'IND') THEN 'I'
      WHEN UPPER({column}) LIKE 'CHURCH%' THEN 'CHURCH'
      ELSE 'other' END"""


def annotate_status_buckets(conn: sqlite3.Connection, run_id: str) -> None:
    """Set each mention's dollar-dominant filer-reported status bucket."""
    started = time.monotonic()
    _log("[dispositions] aggregating filer-reported status per mention…")
    conn.execute(f"""
        CREATE TEMP TABLE dominant_bucket AS
        SELECT mention_id, bucket FROM (
          SELECT g.mention_id,
                 {bucket_case('t.recipient_foundation_status')} AS bucket,
                 SUM(g.signed_amount) AS dollars,
                 ROW_NUMBER() OVER (
                   PARTITION BY g.mention_id
                   ORDER BY SUM(g.signed_amount) DESC
                 ) AS rank
          FROM grant_norm g
          JOIN grant_transactions t ON t.grant_id = g.grant_id
          WHERE g.run_id = ?
          GROUP BY g.mention_id, bucket
        ) WHERE rank = 1
    """, (run_id,))
    _log(f"[dispositions] dominant buckets built in "
         f"{time.monotonic() - started:,.1f}s; indexing + applying…")
    # The correlated-subquery UPDATE needs this index or it goes quadratic
    # over 1.4M mentions x 1.4M temp rows.
    conn.execute("CREATE INDEX temp.idx_dominant ON dominant_bucket(mention_id)")
    conn.execute("""
        UPDATE recipient_mentions AS m SET status_bucket = (
          SELECT bucket FROM dominant_bucket d WHERE d.mention_id = m.mention_id)
        WHERE m.run_id = ?
    """, (run_id,))
    conn.execute("DROP TABLE dominant_bucket")
    _log(f"[dispositions] status buckets applied in "
         f"{time.monotonic() - started:,.1f}s total")


def apply_dispositions(conn: sqlite3.Connection, run_id: str) -> dict[str, int]:
    """Name-pattern pass in Python (chunked), then status/country SQL rules."""
    started = time.monotonic()
    updates: list[tuple[str, str]] = []
    for mention_id, name in conn.execute(
        "SELECT mention_id, name_norm FROM recipient_mentions WHERE run_id=?",
        (run_id,),
    ).fetchall():
        text = name or ""
        if UNATTRIBUTABLE.search(text):
            updates.append(("unattributable", mention_id))
        elif GOVERNMENT.search(text):
            updates.append(("government", mention_id))
    conn.executemany(
        "UPDATE recipient_mentions SET disposition=? "
        "WHERE run_id=? AND mention_id=?",
        [(d, run_id, m) for d, m in updates],
    )
    # Filer-reported statuses and foreign addresses, only where no
    # name-pattern disposition landed first.
    conn.execute("""
        UPDATE recipient_mentions SET disposition='individual'
        WHERE run_id=? AND disposition IS NULL AND status_bucket='I'
    """, (run_id,))
    conn.execute("""
        UPDATE recipient_mentions SET disposition='government'
        WHERE run_id=? AND disposition IS NULL AND status_bucket='GOV'
    """, (run_id,))
    conn.execute("""
        UPDATE recipient_mentions SET disposition='foreign'
        WHERE run_id=? AND disposition IS NULL AND country NOT IN ('US','')
    """, (run_id,))
    counts = dict(conn.execute(
        "SELECT disposition, COUNT(*) FROM recipient_mentions "
        "WHERE run_id=? AND disposition IS NOT NULL GROUP BY 1", (run_id,),
    ).fetchall())
    _log(f"[dispositions] {sum(counts.values()):,} mentions disposed "
         f"in {time.monotonic() - started:,.1f}s: {counts}")
    return counts
