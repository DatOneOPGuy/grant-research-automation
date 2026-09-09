"""The 2026-09 accuracy-audit corrections, pinned.

Every case here was a real error serving in production: $0.85B+ of secular
or non-Christian dollars presented as Christian giving. The classifier fixes
and the read-model corrections pass (build_explorer_v5.
apply_classification_corrections) resolve them; these tests keep them
resolved. The equally important half is the KEEP cases — every fix was
chosen not to disturb a neighbouring genuine classification, and the pins
prove it.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "explorer_v5.db"

sys.path.insert(0, str(ROOT))
from src.classifier import classify  # noqa: E402

CHRISTIAN = ("catholic", "orthodox_christian", "evangelical_protestant",
             "mainline_protestant", "christian_unspecified")


# --- the classifier layer ----------------------------------------------------

@pytest.mark.parametrize("name", [
    # F3 — government bodies. The primary fix is the identity bucket; the
    # name guard stops the same bug re-entering through another pipeline.
    "MINISTRY OF HEALTH RWANDA",
    "FEDERAL MINISTRY OF HEALTH AND SOCIAL WELFARE NIGERIA",
    "MINISTRY OF EDUCATION GHANA",
    # F7 — municipalities.
    "LIGONIER BOROUGH",
    "PARISH OF EAST BATON ROUGE",
    # F2/F6 — secular institutions with heritage names.
    "NEW YORK-PRESBYTERIAN FUND INC",
    "NewYork-Presbyterian Hospital",
    "ST JOHNS COLLEGE",           # Great Books, Santa Fe/Annapolis
    "UNIVERSITY OF ST ANDREWS AMERICAN FOUNDATION INC",
])
def test_secular_and_government_names_are_not_christian(name):
    assert classify(name) != "christian", name


@pytest.mark.parametrize("name", [
    # F4 — Chapel Hill neutralized as a place; F1-adjacent 'frontiers'
    # removal. These become uncategorized or secular, never christian.
    "UNIVERSITY OF NORTH CAROLINA AT CHAPEL HILL",
    "UNC-Chapel Hill",
    "Medecins Sans Frontiers Usa Inc",
    "DIGITAL FRONTIERS INSTITUTE NPC",
])
def test_place_and_vocabulary_leaks_are_closed(name):
    assert classify(name) != "christian", name


@pytest.mark.parametrize("name", [
    # The KEEP side: every fix above must spare these.
    "Chapel Hill Bible Church",          # real church in the town
    "St Johns College High School",      # Catholic, Washington DC
    "ST JOHNS COLLEGE DURHAM",           # Church of England theological
    "Ligonier Ministries",               # the actual ministry
    "Parish of St Mary",                 # a parish, not a civil parish
    "FIRST BAPTIST CHURCH",
    "samaritan's purse",
    "INTERNATIONAL JUSTICE MISSION",
    # NOT "Atlanta Mission": bare 'mission' has never been in the name
    # vocabulary (classify returns None); its christian label came from the
    # now-quarantined grant_purpose method, and it returns via the gold-set
    # readmission or human adjudication. Denver Rescue Mission covers the
    # institution type at the classifier layer.
    "Denver Rescue Mission",
])
def test_neighbouring_genuine_classifications_survive(name):
    assert classify(name) == "christian", name


# --- the read model ----------------------------------------------------------

def _conn():
    if not DB.exists():
        pytest.skip("explorer_v5.db not present")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    if not conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE "
                        "name='classification_conflicts'").fetchone()[0]:
        conn.close()
        pytest.skip("pre-corrections build")
    conn.row_factory = sqlite3.Row
    return conn


CH_SQL = ",".join(f"'{t}'" for t in CHRISTIAN)


def test_no_government_entity_holds_a_religious_tradition():
    """A government body cannot hold a RELIGIOUS tradition ($378M was
    Christian-classified). 'secular' is deliberately KEPT — it is true, and
    clearing it would present the Ministry of Health Rwanda as unknown when
    the product's promise is that unclassified means unknown."""
    conn = _conn()
    n = conn.execute("SELECT COUNT(*) FROM recipients WHERE "
                     "identity_status='government' AND tradition IS NOT NULL "
                     "AND tradition != 'secular'").fetchone()[0]
    secular = conn.execute("SELECT COUNT(*) FROM recipients WHERE "
                           "identity_status='government' AND "
                           "tradition='secular'").fetchone()[0]
    conn.close()
    assert n == 0
    assert secular > 1000, "the secular labels were wrongly cleared too"


def test_grant_purpose_is_out_of_the_numerator():
    """A funder's free text is evidence about the funder, not the recipient.
    UJA-Federation (Jewish) carried christian_unspecified from a purpose
    line reading 'religious organizations ... missions'."""
    conn = _conn()
    n = conn.execute("SELECT COUNT(*) FROM recipients WHERE "
                     "method='grant_purpose'").fetchone()[0]
    conn.close()
    assert n == 0


@pytest.mark.parametrize(("pattern", "why"), [
    ("%UJA%FEDERATION%", "Jewish federation, was $73M christian"),
    ("%DOCTORS WITHOUT BORDERS%", "was $58M christian via 'MEDICAL MISSIONS'"),
    ("%NEW YORK%PRESBYTERIAN HOSPITAL%",
     "secular hospital system, was $150M"),
    ("%NEW YORK-PRESBYTERIAN FUND%", "the system's fund, was $75.6M"),
    ("%MINISTRY OF HEALTH%", "government bodies, were $314M"),
    ("%CAROLINA%CHAPEL HILL%", "the university, was $100M+"),
    ("%UNC%CHAPEL HILL%", "the university's short forms"),
    ("%TENACRE%", "Christian Science, was $77M via BMF NTEE X200"),
])
def test_audit_error_classes_hold_no_christian_dollars(pattern, why):
    conn = _conn()
    d = conn.execute(f"""
        SELECT COALESCE(SUM(total_received),0) FROM recipients
        WHERE tradition IN ({CH_SQL}) AND UPPER(name) LIKE ?""",
        (pattern,)).fetchone()[0]
    conn.close()
    assert d == 0, f"${d/1e6:.1f}M still classified christian — {why}"


@pytest.mark.parametrize(("pattern", "why"), [
    ("%OPEN DOORS SUB SAHARAN%", "foreign bucket kept: genuine ministry"),
    ("%DIOCESE OF LUSAKA%", "foreign bucket kept: genuine diocese"),
    ("%INTERNATIONAL JUSTICE MISSION%",
     "protected from the mission-conflict pass: its mission text has no "
     "religious wording, and demoting IJM would be the worse error"),
    ("%SAMARITAN%PURSE%", "flagship, must never regress"),
    ("NEW YORK AVENUE PRESBYTERIAN CHURCH",
     "a real church on New York Avenue — the NYP fix must spare it"),
    ("CHAPEL HILL UNITED METHODIST%",
     "a real church in the town of Chapel Hill"),
])
def test_genuine_christian_recipients_survive_the_corrections(pattern, why):
    conn = _conn()
    d = conn.execute(f"""
        SELECT COALESCE(SUM(total_received),0) FROM recipients
        WHERE tradition IN ({CH_SQL}) AND UPPER(name) LIKE ?""",
        (pattern,)).fetchone()[0]
    conn.close()
    assert d > 0, why


def test_every_correction_is_on_the_record():
    """The evidence ledger is immutable; the read model's overrides must be
    equally inspectable. Every cleared tradition has a conflicts row saying
    what was cleared and why, and the name-vs-mission rows are the
    human-review inbox the reviewer asked for."""
    conn = _conn()
    kinds = {r["kind"]: r["n"] for r in conn.execute(
        "SELECT kind, COUNT(*) n FROM classification_conflicts GROUP BY 1")}
    conn.close()
    for expected in ("government_bucket", "grant_purpose_quarantine",
                     "rule_recompute", "ein_correction"):
        assert kinds.get(expected), f"no {expected} rows recorded"


def test_the_sol_goldman_page_is_fixed():
    """The reputational case: a prominent Jewish family trust displayed as
    52.6% Christian, 90% of it the NY-Presbyterian error."""
    conn = _conn()
    row = conn.execute("""
        SELECT pct_christian FROM foundations
        WHERE name LIKE '%SOL GOLDMAN CHARITABLE%'""").fetchone()
    conn.close()
    if row is None:
        pytest.skip("foundation not present")
    assert row["pct_christian"] is None or row["pct_christian"] < 15, (
        f"still shows {row['pct_christian']}% Christian")
