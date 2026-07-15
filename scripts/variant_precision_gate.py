"""Precision gate for the suffix/prefix variant match tier.

Samples 50 variant-tier selected matches, stratified by paid dollars and
weighted toward high-dollar rows, and prints filed name vs BMF record for
hand verification. The tier ships only if verified precision >= 98%.
Read-only.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> None:
    conn = sqlite3.connect(
        f"file:{Path('data/grants_v2.db').resolve()}?mode=ro", uri=True, timeout=60)
    conn.execute("ATTACH DATABASE ? AS bmf",
                 (f"file:{Path('data/bmf_registry.db').resolve()}?mode=ro",))
    run_id = conn.execute(
        "SELECT run_id FROM identity_runs ORDER BY created_at_utc DESC LIMIT 1"
    ).fetchone()[0]
    rows = conn.execute(
        """
        SELECT m.display_name, m.city, m.state, m.paid_dollars,
               c.match_method, b.organization_name, b.city, b.state, b.ein,
               b.ntee_code
        FROM recipient_match_candidates c
        JOIN recipient_mentions m
          ON m.run_id=c.run_id AND m.mention_id=c.mention_id
        JOIN bmf.bmf_organizations b ON b.ein=c.candidate_ein
        WHERE c.run_id=? AND c.selected=1 AND c.match_method LIKE 'variant%'
        ORDER BY m.paid_dollars DESC
        """, (run_id,),
    ).fetchall()
    if not rows:
        print("No variant-tier selections found.")
        sys.exit(1)
    n = len(rows)
    total = sum(r[3] for r in rows)
    print(f"Variant tier: {n:,} selected mentions, ${total/1e9:.2f}B "
          f"(run {run_id})\n")
    # Top-20 by dollars, then 30 spread across the remaining range.
    picks = list(range(min(20, n)))
    if n > 20:
        step = max((n - 20) // 30, 1)
        picks += list(range(20, n, step))[:30]
    print("| # (rank) | Filed name | Filed city/st | $ | Method "
          "| BMF name | BMF city/st | EIN | NTEE |")
    print("|---|---|---|---|---|---|---|---|---|")
    for i, rank in enumerate(picks[:50], 1):
        (name, city, st, paid, method, bname, bcity, bst, ein, ntee) = rows[rank]
        print(f"| {i} ({rank+1}) | {(name or '')[:36]} | {(city or '')[:14]}/{st} "
              f"| ${paid/1e6:,.2f}M | {method.replace('variant_','')} "
              f"| {(bname or '')[:36]} | {(bcity or '')[:14]}/{bst} "
              f"| {ein} | {ntee or ''} |")


if __name__ == "__main__":
    main()
