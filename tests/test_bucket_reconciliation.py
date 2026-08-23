"""The stacked bar must account for every paid dollar.

The bar on the Foundations table, the detail header and the Dashboard splits
paid giving into christian / nonchristian / unclassified / DAF. It originally
omitted nonclassifiable_dollars -- money the filing never tied to a named
organisation -- which had two consequences.

Nationally the bar summed to $174B against $236B paid, so $62B simply was not
drawn. And a foundation whose giving is *entirely* unattributable, like the
pharmaceutical patient-assistance funds, summed to zero and fell through to an
empty-state bar whose tooltip read "No paid dollars in window" -- on a
foundation that paid $7.1 billion.

These tests pin the arithmetic the UI depends on.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

DB = Path(__file__).resolve().parents[1] / "data" / "explorer_v5.db"

BUCKETS = ("christian_dollars", "nonchristian_dollars", "unclassified_dollars",
           "daf_dollars", "nonclassifiable_dollars")


def _conn():
    if not DB.exists():
        pytest.skip("explorer_v5.db not present")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def test_the_five_buckets_sum_to_paid_nationally():
    conn = _conn()
    row = conn.execute(
        f"SELECT SUM(paid_2324) paid, {', '.join(f'SUM({b}) {b}' for b in BUCKETS)} "
        "FROM foundations").fetchone()
    conn.close()
    total = sum(row[b] or 0 for b in BUCKETS)
    assert total == row["paid"], (
        f"buckets sum to ${total/1e9:.2f}B against ${row['paid']/1e9:.2f}B "
        f"paid -- ${abs(total - row['paid'])/1e9:.2f}B would go undrawn")


def test_no_foundation_has_paid_dollars_the_buckets_do_not_account_for():
    """Per row, because the national total can net out two opposite errors."""
    conn = _conn()
    bad = conn.execute(
        f"SELECT COUNT(*) FROM foundations WHERE paid_2324 > 0 "
        f"AND paid_2324 != {' + '.join(BUCKETS)}").fetchone()[0]
    conn.close()
    assert bad == 0, f"{bad} foundations whose buckets do not sum to paid"


def test_a_fully_unattributable_foundation_still_draws_a_bar():
    """The case that produced "No paid dollars in window" on $7.1 billion.

    Pharmaceutical patient-assistance funds pay billions that HIPAA forbids
    itemising, so all four original buckets are zero. Including
    nonclassifiable is what stops the bar collapsing to its empty state.
    """
    conn = _conn()
    row = conn.execute("""
        SELECT name, paid_2324, nonclassifiable_dollars,
               christian_dollars + nonchristian_dollars
             + unclassified_dollars + daf_dollars AS four_buckets
        FROM foundations
        WHERE paid_2324 > 1000000000
          AND christian_dollars + nonchristian_dollars
            + unclassified_dollars + daf_dollars = 0
        ORDER BY paid_2324 DESC LIMIT 1""").fetchone()
    conn.close()
    if row is None:
        pytest.skip("no fully unattributable foundation in this build")
    assert row["four_buckets"] == 0, "precondition: the original four are zero"
    assert row["nonclassifiable_dollars"] == row["paid_2324"], (
        f"{row['name']} paid ${row['paid_2324']/1e9:.2f}B but the fifth "
        "bucket does not cover it, so the bar would still render empty")
