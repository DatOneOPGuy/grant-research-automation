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
    assert len(v5.US_STATES) == 56, "50 states + DC + 5 territories"
    for code in ("CA", "TX", "NY", "DC", "PR", "GU"):
        assert code in v5.US_STATES
    for code in ("ON", "ENGLAND", "ARUSHA", "KIGALI", "BRITISH COLUMBIA"):
        assert code not in v5.US_STATES
    assert all(len(c) == 2 for c in v5.US_STATES), "codes only, never names"


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
