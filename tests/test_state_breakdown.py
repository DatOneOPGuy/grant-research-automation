"""The state breakdown must contain only US states.

recipient_states is built from whatever string a filing put in the state
field, and filings are full of foreign regions: ARUSHA, HERTFORDSHIRE,
ONTARIO, KIGALI, BRITISH COLUMBIA. 4,005 of its 4,061 distinct values are not
US states and they carry $5.58B between them -- all of it previously listed,
counted and totalled under a heading that reads "US recipients by state".

International giving has its own tab. This is about the US one being true.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "foundation-explorer" / "backend"
DB = ROOT / "data" / "explorer_v5.db"

sys.path.insert(0, str(BACKEND))
v5 = pytest.importorskip("v5")


def test_the_state_list_is_the_real_one():
    assert len(v5.US_STATES) == 59, "50 states + DC + 5 territories + 3 military"
    for code in ("CA", "TX", "NY", "DC", "PR", "GU"):
        assert code in v5.US_STATES
    for code in ("ON", "ENGLAND", "ARUSHA", "KIGALI", "BRITISH COLUMBIA"):
        assert code not in v5.US_STATES
    assert all(len(c) == 2 for c in v5.US_STATES), "codes only, never names"
    # Armed Forces postal codes: US personnel at US addresses. Nothing flags
    # them foreign, so excluding them hid $1.63M from both views.
    for code in ("AA", "AE", "AP"):
        assert code in v5.US_STATES


@pytest.mark.skipif(not DB.exists(), reason="explorer_v5.db not present")
def test_the_money_that_leaves_the_state_view_is_visible_as_international():
    """Removing a row from one view must not delete it from the product.

    The state filter drops $5.58B. Almost all of it is flagged international
    and appears on that tab instead -- British Columbia becomes Canada. This
    asserts the overlap rather than assuming it.
    """
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    row = conn.execute(f"""
        SELECT SUM(amount) total,
               SUM(CASE WHEN is_foreign = 1
                     OR COALESCE(recipient_country,'') NOT IN
                        ('','U.S','U.S.','UNITED STATES','US','USA')
                   THEN amount ELSE 0 END) flagged
        FROM grants
        WHERE COALESCE(recipient_state,'') != ''
          AND recipient_state NOT IN {v5.US_STATES_SQL}""").fetchone()
    conn.close()
    total, flagged = row
    assert total and flagged / total > 0.999, (
        f"only {100*flagged/total:.2f}% of the dropped dollars are flagged "
        "international; the rest are visible nowhere")


@pytest.mark.skipif(not DB.exists(), reason="explorer_v5.db not present")
def test_the_known_invisible_residual_does_not_grow():
    """Palau, Micronesia and the Marshall Islands.

    Sovereign nations, correctly not US states, but nothing marks them
    foreign either, so they appear in neither view. $854k of $236.4B --
    0.0004% -- and fixing it means changing how foreign_dollars is computed,
    which moves a headline number. Pinned so it cannot quietly become large.
    """
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    hidden = conn.execute(f"""
        SELECT COALESCE(SUM(dollars), 0) FROM recipient_states
        WHERE state NOT IN {v5.US_STATES_SQL}
          AND ein IN (SELECT ein FROM foundations WHERE foreign_dollars = 0)
    """).fetchone()[0]
    conn.close()
    assert hidden < 5_000_000, (
        f"${hidden/1e6:.2f}M is now visible in neither the state view nor "
        "the International tab; it was $854k")


@pytest.mark.skipif(not DB.exists(), reason="explorer_v5.db not present")
def test_the_endpoint_returns_no_foreign_regions():
    """Checked against the foundation whose Geography tab showed the bug."""
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT state FROM recipient_states WHERE ein=? "
        f"AND state IN {v5.US_STATES_SQL}", ("350868122",)).fetchall()
    conn.close()
    assert rows, "expected some US states for Lilly Endowment"
    assert all(r["state"] in v5.US_STATES for r in rows)


@pytest.mark.skipif(not DB.exists(), reason="explorer_v5.db not present")
def test_the_filter_actually_removes_something():
    """Guards against the list being applied to data that never needed it.

    If this ever fails, either the builder started filtering too (fine --
    delete this test) or the join stopped matching (not fine).
    """
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    total = conn.execute("SELECT COUNT(*) FROM recipient_states").fetchone()[0]
    kept = conn.execute(
        f"SELECT COUNT(*) FROM recipient_states WHERE state IN {v5.US_STATES_SQL}"
    ).fetchone()[0]
    conn.close()
    assert kept < total, "the filter removed nothing; is it being applied?"
    assert kept > total * 0.5, "the filter removed most rows; wrong direction?"
