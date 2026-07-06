"""Enrichment pass: composite faith score, Christian-dollar volume, and
per-foundation flags for the prospect-oriented report.

Adds a `foundation_enrich` table keyed by EIN with:
- christian_dollars_2023/24/25, _3yr_total, christian_grant_count_3yr
- total_giving_3yr
- faith_score_pct (percentage-only, preserved), faith_score_composite
  (0.4*pct + 0.6*log-volume) — the volume component surfaces large
  diversified Christian funders that pure-percentage scoring buries
- is_testamentary_trust, is_small_fund, and data-quality flags
"""

import json
import logging
import math
import re
import sqlite3
from collections import defaultdict

from src.config import DB_PATH
from src.faith_config import CONFIDENCE_MIN, FAITH_TAGS
from src.matcher import normalize

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

FAITH_TAG_SET = set(FAITH_TAGS)
VOLUME_CAP = 10_000_000  # $10M+ Christian giving = full volume points
SMALL_FUND = 10_000

# Testamentary-trust / trust-under-will name markers (word-boundary,
# case-insensitive). These are almost always small invite-only memorial
# trusts, unactionable as grant prospects.
TRUST_RE = re.compile(
    r'\b(t\s*/?\s*u\s*/?\s*w|u\s*/?\s*w|uwo|tuw|tua|ttee|'
    r'trust under will|testamentary|char(itable)? (rem|remainder) tr|'
    r'memorial trust)\b',
    re.IGNORECASE,
)


def load_tag_lookup(conn) -> dict[str, set]:
    lookup = {}
    for norm, tags_json in conn.execute(
        "SELECT name_norm, tags FROM recipients WHERE tags != '[]'"
    ):
        tags = {t['name'] for t in json.loads(tags_json)
                if t.get('confidence', 0) >= CONFIDENCE_MIN}
        if tags:
            lookup[norm] = tags
    return lookup


def ensure_table(conn):
    conn.execute("DROP TABLE IF EXISTS foundation_enrich")
    conn.execute("""
        CREATE TABLE foundation_enrich (
            ein TEXT PRIMARY KEY,
            christian_dollars_2023 INTEGER, christian_dollars_2024 INTEGER,
            christian_dollars_2025 INTEGER, christian_dollars_3yr INTEGER,
            christian_grant_count_3yr INTEGER, total_giving_3yr INTEGER,
            faith_score_pct INTEGER, faith_score_composite INTEGER,
            volume_component INTEGER,
            is_testamentary_trust INTEGER, is_small_fund INTEGER,
            is_actively_giving INTEGER
        )
    """)


def composite(pct: float, christian_dollars: int) -> tuple[int, int]:
    """Return (composite_score, volume_component)."""
    vol = 0.0
    if christian_dollars > 0:
        vol = (math.log10(christian_dollars + 1)
               / math.log10(VOLUME_CAP)) * 100
        vol = max(0.0, min(100.0, vol))
    comp = 0.4 * max(0.0, min(100.0, pct)) + 0.6 * vol
    return round(min(100.0, comp)), round(vol)


def run():
    conn = sqlite3.connect(DB_PATH)
    tags = load_tag_lookup(conn)
    log.info("Tagged recipients: %d", len(tags))

    # accumulate per EIN from all grants (2023-2025 window)
    cd_year = defaultdict(lambda: defaultdict(int))   # ein -> year -> $
    cd_total = defaultdict(int)
    cd_count = defaultdict(int)
    tot = defaultdict(int)
    for ein, name, amount, year in conn.execute(
        "SELECT ein, grantee_name, amount, tax_year FROM grants "
        "WHERE grantee_name != ''"
    ):
        ein = ein.zfill(9)
        amount = amount or 0
        if year in (2023, 2024, 2025):
            tot[ein] += amount
        is_faith = bool(tags.get(normalize(name), set()) & FAITH_TAG_SET)
        if is_faith:
            cd_total[ein] += amount
            cd_count[ein] += 1
            if year in (2023, 2024, 2025):
                cd_year[ein][year] += amount
    log.info("Aggregated %d foundations with grants", len(tot))

    # foundation attributes for flags
    names = {}
    small = {}
    active = {}
    for ein, nm, dist in conn.execute(
        "SELECT f.ein, f.organization_name, f.distributions FROM foundations f "
        "JOIN (SELECT ein, MAX(tax_year) y FROM foundations GROUP BY ein) m "
        "ON f.ein = m.ein AND f.tax_year = m.y"
    ):
        e = ein.zfill(9)
        names[e] = nm or ''
        small[e] = 1 if (dist or 0) < SMALL_FUND else 0
        active[e] = 1 if (dist or 0) >= SMALL_FUND else 0

    ensure_table(conn)
    eins = set(tot) | set(cd_total) | set(names)
    written = 0
    for ein in eins:
        total3 = tot.get(ein, 0)
        cdt = cd_total.get(ein, 0)
        pct = (100 * cdt / total3) if total3 > 0 else 0.0
        comp, vol = composite(pct, cdt)
        nm = names.get(ein, '')
        conn.execute(
            "INSERT OR REPLACE INTO foundation_enrich VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ein,
             cd_year[ein].get(2023, 0), cd_year[ein].get(2024, 0),
             cd_year[ein].get(2025, 0), cdt, cd_count.get(ein, 0), total3,
             round(pct), comp, vol,
             1 if TRUST_RE.search(nm) else 0,
             small.get(ein, 0), active.get(ein, 0)),
        )
        written += 1
    conn.commit()

    stats = conn.execute(
        "SELECT SUM(is_testamentary_trust), SUM(is_small_fund), "
        "SUM(CASE WHEN faith_score_composite >= 60 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN christian_dollars_3yr > 0 THEN 1 ELSE 0 END) "
        "FROM foundation_enrich"
    ).fetchone()
    conn.close()
    log.info("Wrote %d enrich rows. Testamentary=%s, small=%s, "
             "composite>=60=%s, any-christian-giving=%s",
             written, *stats)


if __name__ == '__main__':
    run()
