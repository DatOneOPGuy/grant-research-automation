"""The recipients endpoint's location filter.

Recipient location is derived rather than filed -- see build_geo_index -- so
these check that the filter restricts to what it claims and that adding it
does not disturb the endpoint's existing behaviour.
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


@pytest.fixture(scope="module")
def client():
    if not DB.exists():
        pytest.skip("explorer_v5.db not present")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    built = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name='recipient_counties'").fetchone()[0]
    conn.close()
    if not built:
        pytest.skip("recipient_counties not built")
    fastapi = pytest.importorskip("fastapi")
    import v5  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415
    app = fastapi.FastAPI()
    # v5.router already carries prefix="/api/v5"; adding it again here gave
    # every request a 404 that looked like a missing route.
    app.include_router(v5.router)
    return TestClient(app)


def get(client, path):
    r = client.get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
    return r.json()


def test_county_filter_returns_only_that_county(client):
    data = get(client, "/api/v5/recipients"
               "?county=TX|Dallas County&page_size=50")
    assert data["total"] > 0
    for row in data["rows"]:
        assert row["state"] == "TX"
        assert row["county"] == "Dallas County"


def test_the_collision_that_started_this(client):
    """Los Angeles County came back full of San Francisco organisations,
    because every "San ..." city shared the place key "san"."""
    data = get(client, "/api/v5/recipients"
               "?county=CA|Los Angeles County&page_size=50")
    cities = {(r["city"] or "").upper() for r in data["rows"]}
    assert "SAN FRANCISCO" not in cities
    for row in data["rows"]:
        assert row["county"] == "Los Angeles County"


def test_several_counties_union_rather_than_intersect(client):
    """Two counties means either, not both -- no recipient is in two."""
    one = get(client, "/api/v5/recipients?county=TX|Dallas County&page_size=1")
    two = get(client, "/api/v5/recipients"
              "?county=CA|Los Angeles County&page_size=1")
    both = get(client, "/api/v5/recipients"
               "?county=TX|Dallas County,CA|Los Angeles County&page_size=1")
    assert both["total"] == one["total"] + two["total"]


def test_county_narrows_rather_than_replaces_other_filters(client):
    """A location filter has to compose with the classification filters."""
    plain = get(client, "/api/v5/recipients"
                "?county=TX|Dallas County&page_size=1")
    narrowed = get(client, "/api/v5/recipients"
                   "?county=TX|Dallas County&tradition=any_christian"
                   "&page_size=1")
    assert 0 < narrowed["total"] < plain["total"]


def test_state_filter_works_without_a_county(client):
    data = get(client, "/api/v5/recipients?state=RI&page_size=25")
    assert data["total"] > 0
    assert all(r["state"] == "RI" for r in data["rows"])


def test_unfiltered_list_is_unchanged_by_the_join(client):
    """The LEFT JOIN must not drop the ~9% with no location, nor duplicate
    anyone -- either would silently change the headline count."""
    data = get(client, "/api/v5/recipients?page_size=1")
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        expected = conn.execute(
            "SELECT COUNT(*) FROM recipients WHERE total_received > 0"
        ).fetchone()[0]
    assert data["total"] == expected


def test_rows_carry_their_location(client):
    data = get(client, "/api/v5/recipients?county=TX|Dallas County&page_size=5")
    for row in data["rows"]:
        assert row["city"] and row["county"] and row["state"]
        assert row["place_count"] >= 1


def test_malformed_county_is_rejected(client):
    """Without the pipe there is no state, and a bare county name is
    ambiguous -- 31 states have a Washington County."""
    assert client.get("/api/v5/recipients?county=Dallas").status_code == 400


def test_county_picker_scopes(client):
    funders = get(client, "/api/v5/counties?limit=5")
    recipients = get(client, "/api/v5/counties?scope=recipients&limit=5")
    assert all("funders" in r for r in funders["rows"])
    assert all("recipients" in r for r in recipients["rows"])
    assert client.get("/api/v5/counties?scope=nonsense").status_code == 400


def test_county_picker_search_is_literal(client):
    """A LIKE pattern from the user must not act as a wildcard."""
    data = get(client, "/api/v5/counties?scope=recipients&q=%25")
    assert data["rows"] == []
