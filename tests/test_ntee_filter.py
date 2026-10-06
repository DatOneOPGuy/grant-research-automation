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


# --- the Causes tab endpoint --------------------------------------------------

def test_causes_majors_reconcile_with_the_table(api):
    """The tab's per-major dollars must equal foundation_ntee's rollup —
    the same table the filter uses, so the two can never disagree."""
    d = api.get("/api/v5/foundations/562255292/causes").json()
    assert d["majors"]
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    for m in d["majors"]:
        want = conn.execute(
            "SELECT COALESCE(SUM(dollars),0) FROM foundation_ntee "
            "WHERE ein='562255292' AND ntee LIKE ?",
            (m["major"] + "%",)).fetchone()[0]
        assert m["dollars"] == want, m["major"]
    conn.close()
    assert d["coded_dollars"] == sum(m["dollars"] for m in d["majors"])


def test_causes_recipients_carry_their_majors_code(api):
    d = api.get("/api/v5/foundations/562255292/causes").json()
    for m in d["majors"]:
        for r in m["recipients"]:
            assert r["ntee"].startswith(m["major"]), (m["major"], r["ntee"])


def test_causes_recipient_rows_are_capped_but_counted(api):
    """Lilly has hundreds of coded recipients; rows cap at 50 per major
    while recipient_count keeps the true figure."""
    d = api.get("/api/v5/foundations/350868122/causes").json()
    assert any(m["recipient_count"] > 50 for m in d["majors"])
    for m in d["majors"]:
        assert len(m["recipients"]) <= 50
        assert m["recipient_count"] >= len(m["recipients"])


def test_causes_unknown_foundation_is_404(api):
    assert api.get("/api/v5/foundations/000000000/causes").status_code == 404


# --- Emily's custom requests --------------------------------------------------

def test_camp_funders_excludes_the_near_misses(api):
    """The reason this endpoint exists instead of a LIKE: 'camp' as a
    substring hands back Campus Crusade, campaigns and the Campbell
    foundations. Word-boundary matching must keep them out."""
    d = api.get("/api/v5/custom/camp-funders").json()
    assert d["camp_orgs"] > 3000
    assert d["total_funders"] > 5000
    joined = " ".join((f["examples"] or "") for f in d["funders"]).upper()
    for leak in ("CAMPUS", "CAMPAIGN"):
        assert leak not in joined, f"{leak} leaked into the camp examples"


def test_camp_funders_rows_are_verifiable(api):
    """Each returned funder's camp dollars must reconcile against frs for
    at least the top rows — the list is a deliverable Emily hands a client,
    so it gets the same evidence bar as the product."""
    import re as _re
    word = _re.compile(r"\bcamps?\b", _re.IGNORECASE)
    d = api.get("/api/v5/custom/camp-funders").json()
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    for f in d["funders"][:5]:
        rows = conn.execute("""
            SELECT COALESCE(r.display_name, r.name) AS name, frs.dollars
            FROM frs JOIN recipients r ON r.entity_id = frs.entity_id
            WHERE frs.ein = ?""", (f["ein"],)).fetchall()
        camp_dollars = sum(r["dollars"] for r in rows
                           if word.search(r["name"]))
        assert camp_dollars == f["dollars"], f["name"]
    conn.close()
