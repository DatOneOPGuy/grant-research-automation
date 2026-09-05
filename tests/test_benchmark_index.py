"""The international-benchmark list and the filters built on it.

The list is curated, which means a mistake in it is silent: a bad pattern
does not raise, it just labels the wrong foundations as international
prospects. These tests are the thing standing between that and the client.
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

from src.build_benchmark_index import squash  # noqa: E402
from src.international_orgs import (  # noqa: E402
    CATEGORIES,
    ORGS,
    BenchmarkOrg,
    validate,
)

# --- the list itself ---------------------------------------------------------

def test_the_list_is_well_formed():
    validate()


def test_no_duplicate_slugs_or_names():
    slugs = [o.slug for o in ORGS]
    assert len(slugs) == len(set(slugs))


def test_every_category_is_used():
    """A category nobody is in makes an empty heading in the UI."""
    used = {o.category for o in ORGS}
    assert used <= set(CATEGORIES)
    unused = set(CATEGORIES) - used
    assert not unused, f"categories with no ministries: {unused}"


def test_every_pattern_compiles():
    import re
    for org in ORGS:
        for p in (*org.patterns, *org.exclude):
            re.compile(p)


def test_patterns_are_lowercase():
    """Names are squashed to lowercase before matching, so an uppercase
    pattern would silently match nothing."""
    for org in ORGS:
        for p in (*org.patterns, *org.exclude):
            assert p == p.lower(), f"{org.slug}: {p!r} has uppercase"


# --- the specific over-matches that were caught in review --------------------

def _matches(org: BenchmarkOrg, name: str) -> bool:
    import re
    flat = squash(name)
    if not any(re.search(p, flat, re.I) for p in org.patterns):
        return False
    return not any(re.search(p, flat, re.I) for p in org.exclude)


BY_SLUG = {o.slug: o for o in ORGS}

# Every one of these was a real false positive in benchmark_review.csv before
# the patterns were tightened. They are the regression suite for the list.
def test_squash_normalises_punctuation():
    """990-PF schedules spell the same organisation many ways.

    Note squash does NOT make the spellings identical -- an apostrophe
    becomes a space, so "Samaritan's Purse" is "samaritan s purse" while
    "SAMARITANS PURSE" is "samaritans purse". Absorbing that is the
    pattern's job, which is why the pattern is written "samaritan.?s?".
    """
    assert squash("Samaritan's Purse") == "samaritan s purse"
    assert squash("SAMARITANS PURSE") == "samaritans purse"
    assert squash("Samaritan  Purse!") == "samaritan purse"
    # ...and all three reach the same ministry anyway.
    org = BY_SLUG["samaritans-purse"]
    for spelling in ("Samaritan's Purse", "SAMARITANS PURSE",
                     "Samaritan  Purse!"):
        assert _matches(org, spelling), spelling


FALSE_POSITIVES = [
    ("biblica", "ANABAPTIST MENNONITE BIBLICAL SEMINARY"),
    ("biblica", "College of Biblical Studies"),
    ("biblica", "WESLEY BIBLICAL SEMINARY"),
    ("cross-catholic", "HOLY CROSS CATHOLIC SCHOOL"),
    ("cross-catholic", "Holy Cross Catholic Church"),
    ("gideons", "GIDEONS ARMY GRASSROOTS ARMY FOR CHILDREN"),
    ("gideons", "GIDEONS PROMISE INC"),
    ("partners-international", "COMMUNITY PARTNERS INTERNATIONAL"),
    ("partners-international", "MALARIA PARTNERS INTERNATIONAL"),
    ("partners-international", "SOCIAL VENTURE PARTNERS INTERNATIONAL"),
    ("seed-company", "QUALIBASIC SEED COMPANY LIMITED"),
    ("seed-company", "GERMANIA SEED COMPANY"),
    ("unbound", "UNBOUNDED LEARNING INC"),
    ("unbound", "COLLEGE UNBOUND"),
    ("unbound", "TALENT UNBOUND"),
    ("trans-world-radio", "Hostwriter"),
    ("trans-world-radio", "Cartwright Elementary School District No 83"),
    ("hope-international", "MISSIONS OF HOPE INTERNATIONAL"),
    ("hope-international", "Creating Hope International"),
    ("hope-international", "HOPE INTERNATIONAL UNIVERSITY"),
    ("hope-international", "SHARED HOPE INTERNATIONAL"),
    ("world-relief", "Covenant World Relief"),
    ("world-relief", "LUTHERAN WORLD RELIEF INC"),
    ("world-vision", "SMALL WORLD VISION INC"),
    ("billy-graham", "WHEATON COLLEGE BILLY GRAHAM CENTER"),
    ("wycliffe", "Friends of Wycliffe Hall"),
    ("compassion", "COMPASSION AND CHOICES"),
    ("open-doors", "Open Doors Academy"),
    ("pioneers", "YOUTH FRONTIERS INC"),
]


@pytest.mark.parametrize(("slug", "name"), FALSE_POSITIVES)
def test_known_false_positives_stay_excluded(slug, name):
    assert not _matches(BY_SLUG[slug], name), f"{slug} wrongly claims {name!r}"


# These must keep matching -- the fix for the above must not overshoot.
TRUE_POSITIVES = [
    ("biblica", "BIBLICA INC"),
    ("cross-catholic", "CROSS CATHOLIC OUTREACH INC"),
    ("gideons", "GIDEONS INTERNATIONAL"),
    ("gideons", "THE GIDEONS"),
    ("partners-international", "Partners International"),
    ("seed-company", "The Seed Company"),
    ("seed-company", "WYCLIFFE SEED COMPANY"),
    ("unbound", "UNBOUND"),
    ("trans-world-radio", "TRANS WORLD RADIO"),
    ("trans-world-radio", "TransWorld Radio"),
    ("hope-international", "HOPE INTERNATIONAL"),
    ("world-relief", "World Relief Corporation"),
    ("world-vision", "WORLD VISION"),
    ("billy-graham", "Billy Graham Evangelistic Association"),
    ("wycliffe", "WYCLIFFE BIBLE TRANSLATORS INC"),
    ("compassion", "COMPASSION INTERNATIONAL INCORPORATED"),
    ("samaritans-purse", "samaritan's purse"),
    ("samaritans-purse", "SAMARITANS PURSE"),
    ("cru", "Campus Crusade for Christ"),
    ("cru", "Cru"),
    ("open-doors", "OPEN DOORS SUB SAHARAN AFRICA"),
]


@pytest.mark.parametrize(("slug", "name"), TRUE_POSITIVES)
def test_real_ministries_still_match(slug, name):
    assert _matches(BY_SLUG[slug], name), f"{slug} no longer matches {name!r}"


def test_no_ministry_claims_another_ministry():
    """Entries must not overlap -- a foundation would be double-counted
    toward its tier, inflating the commitment signal."""
    for a in ORGS:
        for slug, name in TRUE_POSITIVES:
            if slug == a.slug or not _matches(a, name):
                continue
            pytest.fail(f"{a.slug} also claims {name!r}, which is {slug}")


# --- the built tables --------------------------------------------------------

def _conn():
    if not DB.exists():
        pytest.skip("explorer_v5.db not present")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    built = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name='benchmark_hits'").fetchone()[0]
    if not built:
        conn.close()
        pytest.skip("benchmark index not built")
    conn.row_factory = sqlite3.Row
    return conn


def test_every_ministry_resolved_to_something():
    """An entry matching nothing is nearly always a typo in a pattern."""
    conn = _conn()
    empty = [r["slug"] for r in conn.execute(
        "SELECT slug FROM benchmark_orgs WHERE name_count = 0")]
    conn.close()
    assert not empty, f"matched no recipient at all: {empty}"


def test_name_variants_are_unified():
    """The whole point of patterns over EINs. Samaritan's Purse's largest row
    carries no EIN, so an EIN-only match would drop most of its funders."""
    conn = _conn()
    row = conn.execute(
        "SELECT funders FROM benchmark_orgs WHERE slug='samaritans-purse'"
    ).fetchone()
    conn.close()
    # The single largest row alone has 1,230; unification must beat that.
    assert row["funders"] > 1500, f"only {row['funders']} funders unified"


def test_tiers_are_monotonic():
    """More ministries can never mean more foundations."""
    conn = _conn()
    counts = [r[0] for r in conn.execute("""
        SELECT n FROM (SELECT ein, COUNT(DISTINCT slug) n
        FROM benchmark_hits GROUP BY ein)""")]
    conn.close()
    for tier in (2, 3, 5):
        assert sum(c >= tier for c in counts) <= sum(c >= tier - 1
                                                     for c in counts)


def test_hits_reference_real_orgs():
    conn = _conn()
    orphans = conn.execute(
        "SELECT COUNT(*) FROM benchmark_hits bh WHERE NOT EXISTS "
        "(SELECT 1 FROM benchmark_orgs bo WHERE bo.slug = bh.slug)"
    ).fetchone()[0]
    conn.close()
    assert orphans == 0


# --- the commitment tiers ----------------------------------------------------

@pytest.fixture(scope="module")
def api():
    if not DB.exists():
        pytest.skip("explorer_v5.db not present")
    fastapi = pytest.importorskip("fastapi")
    import v5  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415
    app = fastapi.FastAPI()
    app.include_router(v5.router)  # already carries prefix="/api/v5"
    client = TestClient(app)
    if client.get("/api/v5/benchmark-orgs").status_code != 200:
        pytest.skip("benchmark index not built")
    return client


def test_every_advertised_tier_matches_what_the_filter_returns(api):
    """The counts shown beside each option have to be the number of results
    that option produces, or the control lies about what it will do."""
    tiers = api.get("/api/v5/benchmark-orgs").json()["tiers"]
    assert [t["min"] for t in tiers] == [1, 2, 3, 5]
    for tier in tiers:
        got = api.get("/api/v5/foundations"
                      f"?min_benchmarks={tier['min']}&limit=1").json()["total"]
        assert got == tier["foundations"], (
            f"tier {tier['min']}+ advertises {tier['foundations']:,} "
            f"but the filter returns {got:,}")


def test_tiers_are_cumulative_and_shrink(api):
    """"Three or more" must be a subset of "two or more". They were being
    read as exclusive buckets -- one to four, then five and up -- and the
    counts are what settle it for the reader."""
    tiers = api.get("/api/v5/benchmark-orgs").json()["tiers"]
    counts = [t["foundations"] for t in tiers]
    assert counts == sorted(counts, reverse=True), counts
    assert all(c > 0 for c in counts)


def test_the_lowest_tier_actually_filters_something_out(api):
    """"At least one" is a real filter, not another name for off. It was
    missing entirely, so the only way to express it was to leave the filter
    off -- which returns every foundation in the database."""
    everything = api.get("/api/v5/foundations?limit=1").json()["total"]
    at_least_one = api.get(
        "/api/v5/foundations?min_benchmarks=1&limit=1").json()["total"]
    assert 0 < at_least_one < everything / 10


# --- the second batch, and what counts toward a tier -------------------------

REQUESTED_BATCH_TWO = [
    ("christian-aid-mission", "CHRISTIAN AID MISSION"),
    ("worldventure", "World Venture"),
    ("one-for-israel", "ONE FOR ISRAEL"),
    ("convoy-of-hope", "CONVOY OF HOPE"),
    ("plant-with-purpose", "Plant with Purpose"),
    ("heifer", "HEIFER PROJECT INTERNATIONAL"),
    ("ifcj", "INTERNATIONAL FELLOWSHIP OF CHRISTIANS & JEWS"),
    ("cure-international", "CURE INTERNATIONAL INC"),
    ("focus-on-the-family", "FOCUS ON THE FAMILY"),
    ("young-life", "YOUNG LIFE"),
    ("fca", "FELLOWSHIP OF CHRISTIAN ATHLETES"),
    ("intervarsity", "Intervarsity Christian Fellowship"),
]


@pytest.mark.parametrize(("slug", "name"), REQUESTED_BATCH_TWO)
def test_requested_ministries_match_themselves(slug, name):
    assert _matches(BY_SLUG[slug], name), f"{slug} no longer matches {name!r}"


# Every one of these was a false positive caught in benchmark_review.csv when
# the second batch was added.
BATCH_TWO_FALSE_POSITIVES = [
    # "floresta" is Portuguese for forest; on its own it claimed two Brazilian
    # forest NGOs and a baseball league, about $3M of other people's money.
    ("plant-with-purpose", "INSTITUTO CONEXAO POVOS DA FLORESTA"),
    ("plant-with-purpose", "FLORESTA BASEBALL LEAGUE INC"),
    # Three different organisations, two words apart.
    ("christian-aid-mission", "CHRISTIAN AID MINISTRIES"),
    ("christian-aid-mission", "CHRISTIAN AID CENTER"),
    # An MLM travel company's foundation.
    ("worldventure", "WORLDVENTURES FOUNDATION"),
    ("worldventure", "WORLD VENTURES INC"),
    # A local interfaith council and an unrelated campus ministry.
    ("ifcj", "Palm Beach Fellowship of Christians and Jews"),
    ("ifcj", "FELLOWSHIP OF CHRISTIANS IN UNIVERSITIES AND SCHOOLS"),
    # The publishing house is a separate entity.
    ("intervarsity", "INTER VARSITY PRESS"),
]


@pytest.mark.parametrize(("slug", "name"), BATCH_TWO_FALSE_POSITIVES)
def test_batch_two_false_positives_stay_excluded(slug, name):
    assert not _matches(BY_SLUG[slug], name), f"{slug} wrongly claims {name!r}"


def test_us_facing_ministries_are_flagged_not_dropped():
    """They were requested and are searchable; they just must not inflate the
    commitment tier."""
    from src.international_orgs import NON_INTERNATIONAL_CATEGORIES
    flagged = {o.slug for o in ORGS
               if o.category in NON_INTERNATIONAL_CATEGORIES}
    assert flagged == {"young-life", "fca", "focus-on-the-family",
                       "intervarsity"}, flagged


def test_backend_and_builder_agree_on_what_is_excluded():
    """The backend cannot import from src/, so the list is duplicated. If the
    two drift, the filter and the advertised counts describe different things.
    """
    import v5

    from src.international_orgs import NON_INTERNATIONAL_CATEGORIES
    assert tuple(v5.NON_INTL_CATEGORIES) == tuple(NON_INTERNATIONAL_CATEGORIES)


def test_the_tier_excludes_the_us_facing_ministries(api):
    """Young Life alone has more funders than any five international
    ministries combined. Counting it would make "funds 5+ international
    ministries" mean something else entirely."""
    conn = _conn()
    with_all = conn.execute("""
        SELECT COUNT(*) FROM (
          SELECT ein FROM benchmark_hits GROUP BY ein
          HAVING COUNT(DISTINCT slug) >= 5)""").fetchone()[0]
    conn.close()
    advertised = next(t["foundations"] for t in
                      api.get("/api/v5/benchmark-orgs").json()["tiers"]
                      if t["min"] == 5)
    assert advertised < with_all, (
        "the tier is counting US-facing ministries: "
        f"{advertised:,} advertised vs {with_all:,} counting everything")


def test_us_facing_ministries_are_still_individually_searchable(api):
    """Excluding them from the tier must not make them unfilterable -- being
    able to ask who funds Young Life is why they were added."""
    for slug in ("young-life", "fca", "focus-on-the-family", "intervarsity"):
        total = api.get(
            f"/api/v5/foundations?benchmark={slug}&limit=1").json()["total"]
        assert total > 0, f"{slug} returns nothing"
