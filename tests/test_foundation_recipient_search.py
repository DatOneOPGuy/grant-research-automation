"""Searching one foundation's recipients.

The detail endpoint returns the top 500 by dollars. Lilly Endowment has
2,072 recipients, Gates 2,972 -- so filtering that list in the browser would
search a quarter of them and report "no match" for the rest. That is a false
negative on the only question this table answers, and one the user has no way
to notice. Hence a server-side endpoint over the full set.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "foundation-explorer" / "backend"
DB = ROOT / "data" / "explorer_v5.db"

if not DB.exists():
    pytest.skip("explorer_v5.db not present", allow_module_level=True)

sys.path.insert(0, str(BACKEND))
v5 = pytest.importorskip("v5")

LILLY = "350868122"


def test_it_searches_past_the_top_500():
    """The whole point: a match below the dollar cut must still be found."""
    everything = v5.foundation_recipients(LILLY, q=None, limit=2000)
    assert everything["total"] > 500, "need a foundation with a real tail"
    ranked = [r["name"] for r in everything["rows"]]
    tail = ranked[600]  # comfortably past what the detail endpoint returns
    found = v5.foundation_recipients(LILLY, q=tail, limit=50)
    assert any(r["name"] == tail for r in found["rows"]), (
        f"{tail!r} is recipient 601 by dollars and was not found; the search "
        "is only looking at the visible page")


def test_total_is_the_whole_set_not_the_page():
    page = v5.foundation_recipients(LILLY, q="young", limit=5)
    assert page["total"] > page["matched"], (
        "total must describe the foundation, not the response, or the UI "
        "cannot say 'N of M match'")


def test_name_search_is_case_insensitive_and_partial():
    lower = v5.foundation_recipients(LILLY, q="young life", limit=50)
    upper = v5.foundation_recipients(LILLY, q="YOUNG LIFE", limit=50)
    assert lower["matched"] == upper["matched"] > 0
    assert all("YOUNG LIFE" in r["name"].upper() for r in lower["rows"])


def test_an_ein_finds_exactly_that_recipient():
    seed = v5.foundation_recipients(LILLY, q="young life", limit=10)
    ein = next(r["recipient_ein"] for r in seed["rows"] if r["recipient_ein"])
    hit = v5.foundation_recipients(LILLY, q=ein, limit=10)
    assert hit["matched"] == 1
    assert hit["rows"][0]["recipient_ein"] == ein


@pytest.mark.parametrize("term", ["%", "_", "100%", "a_b", "\\"])
def test_like_wildcards_are_searched_for_literally(term):
    """'%' must mean the character, not "match everything"."""
    out = v5.foundation_recipients(LILLY, q=term, limit=50)
    assert out["matched"] < out["total"], (
        f"{term!r} behaved as a wildcard and matched the whole list")


def test_no_match_is_empty_not_an_error():
    out = v5.foundation_recipients(LILLY, q="zzzznotanorg", limit=10)
    assert out["matched"] == 0 and out["rows"] == []
    assert out["total"] > 0, "total still describes the foundation"
