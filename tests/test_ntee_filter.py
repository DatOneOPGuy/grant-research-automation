"""The NTEE cause-area filter, and its conjoint composition with states.

The conjoint semantic is the whole feature (first-customer request,
2026-09-24): "food security in North Carolina" must mean a K-coded grantee
IN North Carolina -- a funder doing food security in California who also
gives anything in NC is not a lead. Codes exist only for EIN-matched
grantees (~33% of grant dollars), so the filter means "has at least one
matching coded grantee", and these tests hold it to exactly that.
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
def api():
    if not DB.exists():
        pytest.skip("explorer_v5.db not present")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    built = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='foundation_ntee'"
    ).fetchone()[0]
    conn.close()
    if not built:
        pytest.skip("ntee index not built (run src.build_ntee_index)")
    fastapi = pytest.importorskip("fastapi")
    import v5  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415
    app = fastapi.FastAPI()
    app.include_router(v5.router)  # carries its own /api/v5 prefix
    return TestClient(app)


def total(api, qs):
    r = api.get(f"/api/v5/foundations?{qs}&limit=1")
    assert r.status_code == 200, r.text[:200]
    return r.json()["total"]


def test_major_filter_returns_verifiable_funders(api):
    """Every foundation returned under ntee=B must hold a B row in
    foundation_ntee -- checked against the table, not trusted."""
    rows = api.get("/api/v5/foundations?ntee=B&limit=25").json()["rows"]
    assert rows
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    for f in rows:
        n = conn.execute(
            "SELECT COUNT(*) FROM foundation_ntee WHERE ein=? "
            "AND ntee LIKE 'B%'", (f["ein"],)).fetchone()[0]
        assert n > 0, f"{f['name']} returned for ntee=B with no B grantee"
    conn.close()


def test_conjoint_means_the_cause_area_in_those_states(api):
    """The feature: every funder under ntee=K & gives_to_state=NC holds a
    K-coded grantee IN North Carolina, not merely both facts separately."""
    rows = api.get(
        "/api/v5/foundations?ntee=K&gives_to_state=NC&limit=25"
    ).json()["rows"]
    assert rows
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    for f in rows:
        n = conn.execute(
            "SELECT COUNT(*) FROM foundation_ntee WHERE ein=? "
            "AND ntee LIKE 'K%' AND state='NC'", (f["ein"],)).fetchone()[0]
        assert n > 0, f"{f['name']}: no K grantee in NC — independent leak"
    conn.close()


def test_conjoint_is_strictly_narrower_than_either_alone(api):
    k = total(api, "ntee=K")
    k_nc = total(api, "ntee=K&gives_to_state=NC")
    assert 0 < k_nc < k


def test_multi_state_conjoint_widens_across_states(api):
    """DadCamp's case: one cause area across many states must OR the
    states, so adding a state never shrinks the list."""
    one = total(api, "ntee=O&gives_to_state=NC")
    twelve = total(
        api, "ntee=O&gives_to_state=NC,SC,GA,TN,VA,AL,FL,KY,TX,OK,AR,MS")
    assert twelve >= one > 0


def test_ntee_terms_are_or_not_and(api):
    b, q = total(api, "ntee=B"), total(api, "ntee=Q")
    both = total(api, "ntee=B,Q")
    assert max(b, q) <= both <= b + q


def test_full_code_is_narrower_than_its_major(api):
    assert 0 < total(api, "ntee=E86") < total(api, "ntee=E")


def test_composes_with_non_geographic_filters(api):
    plain = total(api, "ntee=Q")
    narrowed = total(api, "ntee=Q&application_status=Accepting Applications")
    assert 0 < narrowed < plain


def test_injection_is_rejected(api):
    for bad in (";DROP", "B%25", "B OR 1=1", "'", "1B"):
        r = api.get(f"/api/v5/foundations?ntee={bad}&limit=1")
        assert r.status_code == 400, f"{bad!r} -> {r.status_code}"


def test_majors_endpoint_counts_match_the_filter(api):
    """The number beside each checkbox must equal what clicking it returns."""
    majors = {r["major"]: r["funders"]
              for r in api.get("/api/v5/ntee-majors").json()["rows"]}
    for m in ("B", "X", "Q"):
        assert majors[m] == total(api, f"ntee={m}"), m
