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


# --- searching by where the money went ---------------------------------------

def test_search_matches_a_county_name():
    """"Which of this funder's recipients are near Dallas" is the same
    question as "which are in Dallas County", and a fundraiser will type
    either."""
    data = v5.foundation_recipients(LILLY, q="Dallas County", limit=100)
    assert data["matched"] > 0
    for row in data["rows"]:
        assert row["county"] == "Dallas County"


def test_search_matches_a_city_name():
    data = v5.foundation_recipients(LILLY, q="Indianapolis", limit=100)
    assert data["matched"] > 0
    for row in data["rows"]:
        assert ((row["city"] or "").upper() == "INDIANAPOLIS"
                or "INDIANAPOLIS" in (row["name"] or "").upper())


def test_a_city_search_reaches_the_rest_of_its_county():
    """The point of carrying the county. Searching Dallas surfaces the
    recipient in Irving, because Irving is in Dallas County -- a fundraiser
    working a metro should not have to guess every suburb's name."""
    data = v5.foundation_recipients(LILLY, q="Dallas", limit=200)
    cities = {(r["city"] or "").upper() for r in data["rows"]
              if r["county"] == "Dallas County"}
    assert len(cities) > 1, f"only one city surfaced: {cities}"
    assert cities - {"DALLAS"}, "nothing outside the city itself was found"


def test_a_bare_state_code_is_matched_as_a_state():
    """"IN" is Indiana, not a substring. Matching two letters as a fragment
    would return every recipient whose name merely contains them."""
    data = v5.foundation_recipients(LILLY, q="TX", limit=100)
    assert data["matched"] > 0
    for row in data["rows"]:
        assert (row["state"] == "TX"
                or "TX" in (row["name"] or "").upper()
                or "TX" in (row["city"] or "").upper())


def test_the_match_count_is_the_real_one_not_the_page_size():
    """This returned len(rows), so a search matching 1,925 recipients
    reported "500" -- the cap, presented as a count, understating in the one
    direction a user cannot check."""
    data = v5.foundation_recipients(LILLY, q="county", limit=25)
    assert data["returned"] == 25
    assert data["matched"] > 25, "matched is still capped by limit"
    assert data["matched"] <= data["total"]


def test_location_is_returned_for_every_row():
    data = v5.foundation_recipients(LILLY, q="Houston", limit=50)
    assert data["rows"]
    for row in data["rows"]:
        assert "city" in row and "county" in row and "state" in row


def test_a_name_search_is_not_broken_by_the_location_columns():
    """Adding the LEFT JOIN must not drop recipients that have no location,
    nor duplicate any that do."""
    named = v5.foundation_recipients(LILLY, q="university", limit=2000)
    ids = [r["entity_id"] for r in named["rows"]]
    assert len(ids) == len(set(ids)), "the join duplicated rows"
    assert named["matched"] == len(ids)
