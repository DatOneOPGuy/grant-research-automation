"""Faith Alignment Score: dollar-weighted, evidence-based, per foundation.

Every component traces to actual grants on the foundation's 990-PFs.
Components (client weights): explicitly Christian 40, churches 15,
missions 15, evangelism 10, education 10, consistency 10.
"""

import json
import logging
import sqlite3
from collections import defaultdict

from src.config import DB_PATH
from src.faith_config import (
    CONFIDENCE_MIN, CONSISTENCY_WEIGHT, FAITH_COMPONENTS, FAITH_TAGS,
    FAITH_TIERS, STAR_TIERS,
)
from src.matcher import normalize

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

FAITH_TAG_SET = set(FAITH_TAGS)


def load_tag_lookup(conn) -> dict[str, set]:
    """name_norm -> set of tag names at/above the confidence floor."""
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS faith_scores (
            ein TEXT PRIMARY KEY,
            faith_alignment_score INTEGER,
            faith_tier TEXT,
            faith_stars TEXT,
            faith_categories TEXT,
            christian_giving_pct REAL,
            years_of_faith_giving INTEGER,
            years_of_giving INTEGER,
            total_giving INTEGER,
            faith_giving INTEGER
        )
    """)


def score_foundation(grants, tag_lookup) -> dict:
    """grants: iterable of (name_norm, amount, tax_year)."""
    total = 0
    comp_dollars = defaultdict(int)
    faith_dollars = 0
    years_all, years_faith = set(), set()
    cat_dollars = defaultdict(int)

    for norm, amount, year in grants:
        amount = amount or 0
        total += amount
        years_all.add(year)
        tags = tag_lookup.get(norm, set())
        faith_hits = tags & FAITH_TAG_SET
        if faith_hits:
            faith_dollars += amount
            years_faith.add(year)
            for t in faith_hits:
                cat_dollars[t] += amount
        for comp, spec in FAITH_COMPONENTS.items():
            if tags & spec['tags']:
                comp_dollars[comp] += amount

    if total <= 0:
        return None

    score = 0.0
    for comp, spec in FAITH_COMPONENTS.items():
        score += spec['weight'] * (comp_dollars[comp] / total)
    if years_all:
        score += CONSISTENCY_WEIGHT * (len(years_faith) / len(years_all))
    score = min(round(score), 100)

    tier = next(t for cutoff, t in FAITH_TIERS if score >= cutoff)
    stars = next(s for cutoff, s in STAR_TIERS if score >= cutoff)
    categories = sorted(cat_dollars, key=cat_dollars.get, reverse=True)

    return {
        'faith_alignment_score': score,
        'faith_tier': tier,
        'faith_stars': stars,
        'faith_categories': '; '.join(categories),
        'christian_giving_pct': round(100 * faith_dollars / total, 1),
        'years_of_faith_giving': len(years_faith),
        'years_of_giving': len(years_all),
        'total_giving': total,
        'faith_giving': faith_dollars,
    }


def run():
    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)
    tag_lookup = load_tag_lookup(conn)
    log.info("Tagged recipients in lookup: %d", len(tag_lookup))

    by_ein = defaultdict(list)
    for ein, name, amount, year in conn.execute(
        "SELECT ein, grantee_name, amount, tax_year FROM grants "
        "WHERE grantee_name != ''"
    ):
        by_ein[ein].append((normalize(name), amount, year))
    log.info("Scoring %d foundations with grants...", len(by_ein))

    written = 0
    for ein, grants in by_ein.items():
        result = score_foundation(grants, tag_lookup)
        if result is None:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO faith_scores VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ein, *[result[k] for k in (
                'faith_alignment_score', 'faith_tier', 'faith_stars',
                'faith_categories', 'christian_giving_pct',
                'years_of_faith_giving', 'years_of_giving',
                'total_giving', 'faith_giving')]),
        )
        written += 1
    conn.commit()

    dist = conn.execute(
        "SELECT faith_tier, COUNT(*) FROM faith_scores "
        "GROUP BY faith_tier ORDER BY COUNT(*) DESC"
    ).fetchall()
    log.info("Wrote %d faith scores. Tier distribution:", written)
    for tier, count in dist:
        log.info("  %-38s %d", tier, count)
    conn.close()


if __name__ == '__main__':
    run()
