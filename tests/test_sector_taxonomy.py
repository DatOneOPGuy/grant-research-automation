"""Cause-area classification of the non-Christian bucket.

Two kinds of test here. The first group is pure taxonomy and always runs: the
mapping has to be total, the categories have to be disjoint, and the name
fallback has to stay conservative. The second group checks the built index in
explorer_v5.db and skips when it has not been built, because the invariant
that matters -- the sector totals reconcile to the read model's own
non-Christian figure -- can only be checked against real data.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sector_taxonomy import (  # noqa: E402
    METHOD_CONFIDENCE,
    NTEE_MAJOR,
    SECTOR_ORDER,
    SECTORS,
    TRADITION_SECTOR,
    sector_from_name,
    sector_from_ntee,
)

DB = ROOT / "data" / "explorer_v5.db"


# --- taxonomy ----------------------------------------------------------------

def test_every_ntee_major_group_maps_somewhere():
    """A-Z with no gaps. An unmapped letter silently becomes 'unknown'."""
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        assert letter in NTEE_MAJOR, f"NTEE group {letter} is unmapped"


def test_every_mapping_target_is_a_declared_sector():
    for source in (NTEE_MAJOR, TRADITION_SECTOR):
        for key, sector in source.items():
            assert sector in SECTORS, f"{key} maps to undeclared {sector!r}"


def test_display_order_covers_every_sector_exactly_once():
    assert sorted(SECTOR_ORDER) == sorted(SECTORS)
    assert len(SECTOR_ORDER) == len(set(SECTOR_ORDER))


def test_grantmaking_is_not_filed_as_a_cause():
    """NTEE T is a transfer to another grantmaker, not a cause area.

    $24.1B of the non-Christian total is T-coded, and the largest single item
    is Gates Foundation Trust funding its own operating foundation. Counting
    that as giving to a cause asserts a destination nobody knows.
    """
    assert NTEE_MAJOR["T"] == "regranting"
    assert sector_from_ntee("T22") == "regranting"
    assert sector_from_ntee("T31") == "regranting"


def test_faith_specific_ntee_codes_beat_the_generic_religion_group():
    assert sector_from_ntee("X30") == "faith_jewish"
    assert sector_from_ntee("X40") == "faith_muslim"
    # No specific faith: stays unspecified rather than being guessed at.
    assert sector_from_ntee("X99") == "religion_unspecified"
    assert sector_from_ntee("X20") == "religion_unspecified"


@pytest.mark.parametrize("code,expected", [
    ("B43", "education"), ("E22", "health"), ("H12", "health"),
    ("P20", "human_services"), ("L21", "human_services"),
    ("O50", "youth"), ("N60", "youth"), ("A51", "arts"),
    ("Q33", "international"), ("C34", "environment"), ("D20", "environment"),
    ("R22", "civic"), ("S30", "civic"), ("U40", "science"),
])
def test_representative_codes_land_in_the_right_sector(code, expected):
    assert sector_from_ntee(code) == expected


@pytest.mark.parametrize("value", [None, "", "   ", "?", "1"])
def test_unusable_ntee_values_return_nothing(value):
    assert sector_from_ntee(value) is None


def test_lowercase_ntee_is_handled():
    assert sector_from_ntee("b43") == "education"


# --- the name fallback -------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("Emory University", "education"),
    ("Massachusetts General Hospital", "health"),
    ("THE METROPOLITAN MUSEUM OF ART", "arts"),
    ("Greater Boston Food Bank", "human_services"),
    ("NATURE CONSERVANCY", "environment"),
    ("YMCA of Greater Seattle", "youth"),
    ("AMERICAN RED CROSS", "international"),
    ("Community Foundation of New Jersey", "regranting"),
])
def test_name_rules_catch_the_unambiguous_cases(name, expected):
    assert sector_from_name(name) == expected


@pytest.mark.parametrize("name", [
    # Every one of these spans multiple sectors. Guessing would be worse than
    # admitting we do not know.
    "The Smith Family Foundation", "Anderson Charitable Trust",
    "Community Fund", "The Wilson Institute", "Riverside Center",
    "National Association of Widgets", "Society for Progress",
    "Helping Hands", "The Legacy Group",
])
def test_ambiguous_names_are_left_alone(name):
    assert sector_from_name(name) is None


@pytest.mark.parametrize("name", [
    "Scholastic Book Clubs",       # 'school' must not match inside 'Scholastic'
    "Clinical Trials Registry",    # 'clinic' must not match inside 'Clinical'
    "Academia Research Group",     # 'academy' must not match 'Academia'
    "Collegiality Project",        # 'college' must not match 'Collegiality'
])
def test_name_rules_do_not_match_inside_longer_words(name):
    """Substring matching would be far worse than no matching at all."""
    assert sector_from_name(name) is None


def test_name_rules_are_known_to_be_fallible():
    """Documents the limitation rather than pretending it does not exist.

    "Universities Superannuation Scheme" is a pension fund, and the education
    rule matches it on the word "Universities". Word boundaries stop
    substring accidents, not homographs, and no keyword list will. This is
    why every name-derived sector is labelled low confidence and why the UI
    says "mostly inferred" instead of presenting it as fact.
    """
    assert sector_from_name("Universities Superannuation Scheme") == "education"
    assert METHOD_CONFIDENCE["name_rule"] == "low"


def test_confidence_is_declared_for_every_method():
    for method in ("tradition", "ntee_ein", "ntee_name", "name_rule"):
        assert method in METHOD_CONFIDENCE
    assert METHOD_CONFIDENCE["ntee_ein"] == "high"
    assert METHOD_CONFIDENCE["name_rule"] == "low", (
        "a sector inferred from a name must never be presented as strongly "
        "as one the IRS assigned")


# --- the built index ---------------------------------------------------------

def _conn():
    if not DB.exists():
        pytest.skip("explorer_v5.db not present")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    built = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name IN ('recipient_sectors','sector_stats')").fetchone()[0]
    if built < 2:
        conn.close()
        pytest.skip("sector index not built (run src.build_sector_index)")
    return conn


def test_sector_totals_reconcile_to_the_read_model():
    """The decomposition must add up to the number it decomposes.

    If these drift, the breakdown is describing a different population than
    the headline figure and one of them is lying.
    """
    conn = _conn()
    headline = conn.execute(
        "SELECT SUM(nonchristian_dollars) FROM foundations").fetchone()[0]
    decomposed = conn.execute(
        "SELECT SUM(dollars) FROM sector_stats WHERE tier='all'").fetchone()[0]
    conn.close()
    assert headline and decomposed
    drift = abs(headline - decomposed) / headline
    assert drift < 0.001, (
        f"sector total ${decomposed/1e9:.2f}B vs non-Christian "
        f"${headline/1e9:.2f}B ({100*drift:.2f}% apart)")


def test_no_christian_recipient_is_given_a_sector():
    """Sectors describe the non-Christian bucket only.

    Leaking a Christian recipient in would double-count it: it is already in
    christian_dollars, and the breakdown claims to partition what is left.
    """
    conn = _conn()
    leaked = conn.execute("""
        SELECT COUNT(*) FROM recipient_sectors s
        JOIN recipients r ON r.entity_id = s.entity_id
        WHERE r.tradition IN ('evangelical_protestant','catholic',
                              'orthodox_christian','christian_unspecified')
           OR r.is_daf = 1""").fetchone()[0]
    conn.close()
    assert leaked == 0, f"{leaked} Christian or DAF recipients were given a sector"


def test_every_recipient_in_the_bucket_gets_exactly_one_sector():
    conn = _conn()
    expected = conn.execute("""
        SELECT COUNT(*) FROM recipients
        WHERE is_daf = 0 AND tradition IN
          ('jewish','muslim','mormon_lds','christian_science',
           'other_religion','secular','nonchristian_unspecified')""").fetchone()[0]
    got = conn.execute("SELECT COUNT(*) FROM recipient_sectors").fetchone()[0]
    conn.close()
    assert got == expected


def test_every_assigned_sector_is_in_the_taxonomy():
    conn = _conn()
    found = {r[0] for r in conn.execute(
        "SELECT DISTINCT sector FROM recipient_sectors")}
    conn.close()
    assert found <= set(SECTORS), f"undeclared sectors in the data: {found - set(SECTORS)}"


def test_confidence_columns_reconcile_to_the_row_total():
    """The precomputed evidence split must add up to the row it splits.

    These four columns exist because deriving them at query time cost 525ms
    on a large foundation. Precomputing trades a live join for a value that
    can go stale, so the reconciliation is asserted rather than assumed.
    """
    conn = _conn()
    row = conn.execute("""
        SELECT SUM(dollars), SUM(d_high + d_medium + d_low + d_none)
        FROM sector_stats WHERE tier='all'""").fetchone()
    bad = conn.execute("""
        SELECT COUNT(*) FROM sector_stats
        WHERE dollars != d_high + d_medium + d_low + d_none""").fetchone()[0]
    conn.close()
    assert row[0] == row[1], f"{row[0]} != {row[1]}"
    assert bad == 0, f"{bad} rows whose confidence split misses their total"


def test_a_foundations_sectors_sum_to_its_non_christian_total():
    """Per-foundation, not just nationally: the breakdown is of THIS funder."""
    conn = _conn()
    mismatches = conn.execute("""
        SELECT COUNT(*) FROM (
          SELECT f.ein, f.nonchristian_dollars AS headline,
                 (SELECT COALESCE(SUM(dollars),0) FROM sector_stats s
                  WHERE s.ein=f.ein AND s.tier='all') AS decomposed
          FROM foundations f WHERE f.nonchristian_dollars > 0)
        WHERE ABS(headline - decomposed) > 1""").fetchone()[0]
    conn.close()
    assert mismatches == 0, (
        f"{mismatches} foundations whose sector rows do not sum to their "
        "non-Christian figure")


def test_the_precomputed_national_rollup_matches_the_live_aggregate():
    """sector_totals is a cache of a GROUP BY; caches drift."""
    conn = _conn()
    cached = dict(conn.execute("SELECT sector, dollars FROM sector_totals"))
    live = dict(conn.execute(
        "SELECT sector, SUM(dollars) FROM sector_stats WHERE tier='all' "
        "GROUP BY sector"))
    conn.close()
    assert cached == live, "sector_totals disagrees with sector_stats"


def test_most_dollars_rest_on_irs_evidence_not_inference():
    """A breakdown mostly built from name guesses would not be worth showing."""
    conn = _conn()
    rows = dict(conn.execute("""
        SELECT COALESCE(s.confidence,'none'), SUM(g.amount)
        FROM grants g JOIN recipient_sectors s ON s.entity_id = g.entity_id
        GROUP BY 1"""))
    conn.close()
    total = sum(rows.values())
    assert rows.get("high", 0) / total > 0.6, (
        f"only {100*rows.get('high',0)/total:.0f}% of sector dollars are "
        "high-confidence")
