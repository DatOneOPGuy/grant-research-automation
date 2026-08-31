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
from src.geo_regions import is_placeholder, place_keys  # noqa: E402

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
    assert "indianapolis" in place_keys("Indianapolis city (balance)")
    assert place_keys("Dover city") == place_keys("DOVER")
    assert place_keys("FT MITCHELL") == place_keys("Fort Mitchell city")
    assert place_keys("ST LOUIS") == place_keys("Saint Louis city")


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
