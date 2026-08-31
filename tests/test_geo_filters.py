"""Regions and counties.

Two levels of geography above and below the state, both derived rather than
filed. Regions are a mapping over the state code -- if a grant has a state it
has a region, so there is no coverage loss. Counties are matched from the city
on the filing, which places 89.5% of US dollars; the rest is filings that
wrote "VARIOUS" or "See Attached" where a city goes.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "foundation-explorer" / "backend"
DB = ROOT / "data" / "explorer_v5.db"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))
regions = pytest.importorskip("regions")
from src.geo_regions import is_placeholder, place_alias, place_key, place_keys  # noqa: E402

# --- regions ----------------------------------------------------------------

def test_every_us_state_has_a_region():
    """A state without one would vanish from region filtering silently."""
    import v5
    for code in v5.US_STATES:
        assert regions.region_of(code), f"{code} has no region"
        assert regions.division_of(code), f"{code} has no division"


def test_regions_partition_the_states():
    """No state in two regions, which would double-count it."""
    seen: dict[str, str] = {}
    for name in regions.REGIONS:
        for state in regions.states_in_region(name):
            assert state not in seen, f"{state} is in {seen[state]} and {name}"
            seen[state] = name


def test_divisions_roll_up_into_their_region():
    for state, (region, division) in regions.DIVISIONS.items():
        assert state in regions.states_in_region(region)
        assert state in regions.states_in_region(division)


def test_known_placements():
    assert regions.region_of("TX") == "South"
    assert regions.division_of("TX") == "West South Central"
    assert regions.region_of("ME") == "Northeast"
    assert regions.division_of("CA") == "Pacific"
    # Territories and military codes are their own bucket, not folded into a
    # mainland region they are not part of.
    assert regions.region_of("PR") == "Territories"
    assert regions.region_of("AE") == "Territories"


# --- the city -> county crosswalk -------------------------------------------

def test_place_keys_reach_census_spellings():
    """A filing writes "NASHVILLE"; the file says "Nashville-Davidson
    metropolitan government (balance)". They have to meet."""
    assert "nashville" in place_keys("Nashville-Davidson metropolitan "
                                     "government (balance)")
    assert "louisville" in place_keys("Louisville/Jefferson County metro "
                                      "government (balance)")
    assert place_key("Indianapolis city (balance)") == "indianapolis"
    assert place_key("Dover city") == place_key("DOVER")
    assert place_key("FT MITCHELL") == place_key("Fort Mitchell city")
    assert place_key("ST LOUIS") == place_key("Saint Louis city")


@pytest.mark.parametrize("name", [
    "San Francisco city", "New York city", "Los Angeles city",
    "Fort Worth city", "Saint Paul city", "Kansas City city",
])
def test_multi_word_names_have_no_bare_first_word_alias(name):
    """The bug this exists to prevent.

    place_keys used to append the first word of any multi-word name, so every
    "San ..." city in California shared the key "san" and every "New ..." the
    key "new". One place won that vote and captured the rest, which is how a
    filter for Los Angeles County came back full of San Francisco
    organisations. Only hyphenated and slashed names get an alias now.
    """
    assert place_alias(name) == "", f"{name} should not have an alias"
    assert place_keys(name) == [place_key(name)]


def test_place_keys_are_ordered_exact_name_first():
    """county_of takes the first key that resolves, so the exact name has to
    come before the looser alias. This was a set, and set order is arbitrary
    -- the alias sometimes won by accident."""
    keys = place_keys("Nashville-Davidson metropolitan government (balance)")
    assert isinstance(keys, list)
    assert keys[0] == "nashville davidson"
    assert keys[1] == "nashville"


@pytest.mark.parametrize("value", [
    "VARIOUS", "various", "NA", "See Attached", "Unknown", "none", "Multiple",
])
def test_placeholders_are_not_places(value):
    """These must not be matched to a real county."""
    assert is_placeholder(value)


@pytest.mark.parametrize("value", ["Dover", "New York", "Kansas City"])
def test_real_places_are_not_placeholders(value):
    assert not is_placeholder(value)


# --- the built table --------------------------------------------------------

def _conn():
    if not DB.exists():
        pytest.skip("explorer_v5.db not present")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    built = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name='foundation_counties'").fetchone()[0]
    if not built:
        conn.close()
        pytest.skip("county index not built (run src.build_geo_index)")
    conn.row_factory = sqlite3.Row
    return conn


def test_no_county_name_carries_the_multi_county_separator():
    """The Census file separates multiple counties with "~~~", not a comma.

    Splitting on a comma produced names like "Bronx County~~~Kings County~~~
    New York County" on 101,167 rows carrying $37.55B.
    """
    conn = _conn()
    bad = conn.execute(
        "SELECT COUNT(*) FROM foundation_counties WHERE county LIKE '%~%'"
    ).fetchone()[0]
    conn.close()
    assert bad == 0, f"{bad} rows have an unsplit multi-county name"


def test_the_county_count_is_plausible():
    """3,143 counties, plus DC and territory equivalents."""
    conn = _conn()
    n = conn.execute(
        "SELECT COUNT(DISTINCT state || '|' || county) FROM foundation_counties"
    ).fetchone()[0]
    conn.close()
    assert 3_000 < n < 3_300, f"{n} distinct counties is not a US county count"


def test_new_york_city_files_under_new_york_county():
    """NYC spans five counties and the file lists them alphabetically, so
    taking the first would put all of it in the Bronx."""
    conn = _conn()
    row = conn.execute("""
        SELECT county, SUM(dollars) d FROM foundation_counties
        WHERE state='NY' GROUP BY county ORDER BY d DESC LIMIT 1""").fetchone()
    conn.close()
    assert row["county"] == "New York County"


def test_county_dollars_do_not_exceed_state_dollars():
    """A county rollup larger than its state means double counting."""
    conn = _conn()
    bad = conn.execute("""
        SELECT COUNT(*) FROM (
          SELECT fc.ein, fc.state, SUM(fc.dollars) c,
                 (SELECT rs.dollars FROM recipient_states rs
                  WHERE rs.ein=fc.ein AND rs.state=fc.state) s
          FROM foundation_counties fc GROUP BY fc.ein, fc.state)
        WHERE s IS NOT NULL AND c > s + 1""").fetchone()[0]
    conn.close()
    assert bad == 0, f"{bad} (funder, state) pairs have counties exceeding the state"


def test_distinct_cities_do_not_collapse_into_one_county():
    """Places that merely share a first word must land separately."""
    conn = _conn()
    got = {}
    for city in ("SAN FRANCISCO", "SAN LUIS OBISPO", "SAN DIEGO"):
        row = conn.execute(
            "SELECT county FROM recipient_counties WHERE UPPER(city)=? "
            "AND state='CA' GROUP BY county ORDER BY COUNT(*) DESC LIMIT 1",
            (city,)).fetchone()
        if row:
            got[city] = row["county"]
    conn.close()
    assert len(set(got.values())) == len(got), f"collapsed together: {got}"
    assert got.get("SAN FRANCISCO") == "San Francisco County"


def test_recipient_locations_agree_with_their_city():
    """Spot-check consolidated governments, where city name != county name."""
    conn = _conn()
    for city, state, county in (
        ("NASHVILLE", "TN", "Davidson County"),
        ("LOUISVILLE", "KY", "Jefferson County"),
        ("BROOKLYN", "NY", "Kings County"),
        ("PASADENA", "CA", "Los Angeles County"),
    ):
        row = conn.execute(
            "SELECT county FROM recipient_counties WHERE UPPER(city)=? "
            "AND state=? GROUP BY county ORDER BY COUNT(*) DESC LIMIT 1",
            (city, state)).fetchone()
        assert row, f"{city} placed nowhere"
        assert row["county"] == county, f"{city} -> {row['county']}"
    conn.close()


def test_every_recipient_has_exactly_one_location():
    """An organisation has an address. Two rows would double-count it in any
    county filter."""
    conn = _conn()
    dupes = conn.execute(
        "SELECT COUNT(*) FROM (SELECT entity_id FROM recipient_counties "
        "GROUP BY entity_id HAVING COUNT(*) > 1)").fetchone()[0]
    conn.close()
    assert dupes == 0
