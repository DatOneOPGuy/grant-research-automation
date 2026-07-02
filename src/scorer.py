"""Score foundations from matches.csv against 990 data in SQLite."""

import re
import sqlite3
import logging

import pandas as pd

from src.config import (
    DB_PATH, TARGET_ORGANIZATIONS, KEYWORD_CLUSTERS,
    ALL_KEYWORDS, COMPOUND_KEYWORDS, KEYWORD_FIELD_WEIGHTS,
    CLUSTER_BONUS_TWO, CLUSTER_BONUS_ALL, SCORE_WEIGHTS,
    RECENCY_MULTIPLIER, GRANTEE_POINT_SCHEDULE,
    GRANTEE_5TH_PLUS_PTS, GRANTEE_LARGE_DONATION_THRESHOLD,
    GRANTEE_LARGE_DONATION_BONUS, GRANTEE_MAX_LARGE_BONUS,
)
from src.matcher import (
    normalize, find_match, match_grantee_to_targets,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)


def build_target_lookup() -> dict[str, str]:
    """Build normalized target name → canonical name lookup."""
    lookup = {}
    for org in TARGET_ORGANIZATIONS:
        lookup[normalize(org)] = org
    return lookup


def build_foundation_candidates(conn) -> list[dict]:
    """Build candidate list from SQLite foundations table."""
    rows = conn.execute(
        "SELECT DISTINCT ein, organization_name, city, state "
        "FROM foundations"
    ).fetchall()

    candidates = []
    for ein, name, city, state in rows:
        candidates.append({
            'ein': ein,
            'name': name,
            'normed': normalize(name),
            'city': city or '',
            'state': state or '',
        })
    return candidates


def score_grantee_matches(conn, ein, target_lookup):
    """
    Score section A: Past Grantee Matches (0-35 pts).
    Returns (score, matched_orgs_list, match_count).
    """
    grants = conn.execute(
        "SELECT grantee_name, amount, tax_year "
        "FROM grants WHERE ein = ?",
        (ein,),
    ).fetchall()

    matched_orgs = {}  # canonical_name → max_amount
    for grantee_name, amount, tax_year in grants:
        canonical = match_grantee_to_targets(
            grantee_name, target_lookup
        )
        if canonical:
            recency = RECENCY_MULTIPLIER.get(tax_year, 1.0)
            adj_amount = (amount or 0) * recency
            if canonical not in matched_orgs:
                matched_orgs[canonical] = adj_amount
            else:
                matched_orgs[canonical] = max(
                    matched_orgs[canonical], adj_amount
                )

    if not matched_orgs:
        return 0, [], 0

    # Calculate points with diminishing returns
    points = 0
    schedule = GRANTEE_POINT_SCHEDULE
    for i, org in enumerate(matched_orgs):
        if i < len(schedule):
            points += schedule[i]
        else:
            points += GRANTEE_5TH_PLUS_PTS

    # Large donation bonus
    large_bonus = 0
    for org, amount in matched_orgs.items():
        if amount > GRANTEE_LARGE_DONATION_THRESHOLD:
            large_bonus += GRANTEE_LARGE_DONATION_BONUS
    large_bonus = min(large_bonus, GRANTEE_MAX_LARGE_BONUS)
    points += large_bonus

    cap = SCORE_WEIGHTS['grantee']
    return min(points, cap), list(matched_orgs.keys()), len(matched_orgs)


def _find_keywords_in_text(text: str) -> set[str]:
    """Find all matching keywords in a text string."""
    if not text:
        return set()

    text_lower = text.lower()
    found = set()

    # Check compound phrases first
    for phrase in COMPOUND_KEYWORDS:
        if phrase.lower() in text_lower:
            found.add(phrase)

    # Check single keywords (word boundary, allow plural/suffix)
    for kw in ALL_KEYWORDS:
        if kw in found:
            continue  # Already matched as compound
        pattern = r'\b' + re.escape(kw.lower()) + r'(s|es|ing|al)?\b'
        if re.search(pattern, text_lower):
            found.add(kw)

    return found


def _keyword_cluster(keyword: str) -> str | None:
    """Return which cluster a keyword belongs to."""
    for cluster_name, keywords in KEYWORD_CLUSTERS.items():
        if keyword in keywords:
            return cluster_name
    return None


def score_keywords(conn, ein):
    """
    Score section B: Keyword Matches (0-30 pts).
    Returns (score, matched_keywords_list, match_count).
    """
    # Gather text from each field type
    activities = conn.execute(
        "SELECT description FROM charitable_activities WHERE ein = ?",
        (ein,),
    ).fetchall()
    activity_text = ' '.join(row[0] for row in activities if row[0])

    grants = conn.execute(
        "SELECT purpose FROM grants WHERE ein = ?",
        (ein,),
    ).fetchall()
    grant_text = ' '.join(row[0] for row in grants if row[0])

    org_name = conn.execute(
        "SELECT organization_name FROM foundations WHERE ein = ? "
        "LIMIT 1",
        (ein,),
    ).fetchone()
    org_text = org_name[0] if org_name else ''

    # Find keywords in each field
    activity_kws = _find_keywords_in_text(activity_text)
    grant_kws = _find_keywords_in_text(grant_text)
    org_kws = _find_keywords_in_text(org_text)

    # Score with field weights (avoid double-counting)
    all_found = activity_kws | grant_kws | org_kws
    points = 0
    for kw in all_found:
        # Use highest weight field where keyword was found
        weight = 0
        if kw in activity_kws:
            weight = max(weight, KEYWORD_FIELD_WEIGHTS['charitable_activities'])
        if kw in grant_kws:
            weight = max(weight, KEYWORD_FIELD_WEIGHTS['grant_purpose'])
        if kw in org_kws:
            weight = max(weight, KEYWORD_FIELD_WEIGHTS['organization_name'])
        points += weight

    # Cluster bonus
    clusters_hit = set()
    for kw in all_found:
        cluster = _keyword_cluster(kw)
        if cluster:
            clusters_hit.add(cluster)

    if len(clusters_hit) >= 3:
        points += CLUSTER_BONUS_ALL
    elif len(clusters_hit) >= 2:
        points += CLUSTER_BONUS_TWO

    cap = SCORE_WEIGHTS['keyword']
    return min(points, cap), sorted(all_found), len(all_found)


def score_international(conn, ein):
    """
    Score section C: International Giving (0-25 pts).
    Returns (score, gives_internationally_bool).
    """
    grants = conn.execute(
        "SELECT is_foreign, country FROM grants WHERE ein = ?",
        (ein,),
    ).fetchall()

    if not grants:
        return 0, False

    total = len(grants)
    foreign = [g for g in grants if g[0] == 1]
    foreign_count = len(foreign)
    countries = set(g[1] for g in foreign if g[1] and g[1] != 'US')

    points = 0

    # Any foreign grants: 10 pts
    if foreign_count > 0:
        points += 10

    # >25% international: +8 pts
    if total > 0 and (foreign_count / total) > 0.25:
        points += 8

    # 2+ different countries: +7 pts
    if len(countries) >= 2:
        points += 7

    cap = SCORE_WEIGHTS['international']
    return min(points, cap), foreign_count > 0


def score_focus_area(conn, ein):
    """
    Score section D: Focus Area / Mission Alignment (0-10 pts).
    """
    # Check charitable activities for faith/international terms
    activities = conn.execute(
        "SELECT description FROM charitable_activities WHERE ein = ?",
        (ein,),
    ).fetchall()
    activity_text = ' '.join(
        row[0] for row in activities if row[0]
    ).lower()

    faith_terms = [
        'religion', 'religious', 'faith', 'christian', 'church',
        'ministry', 'gospel', 'bible', 'missionary',
    ]
    intl_terms = [
        'international', 'global', 'foreign', 'overseas',
        'developing countries', 'humanitarian',
    ]

    points = 0

    # Purpose mentions faith/religion (up to 4 pts)
    faith_hits = sum(1 for t in faith_terms if t in activity_text)
    points += min(faith_hits, 4)

    # Purpose mentions international (up to 3 pts)
    intl_hits = sum(1 for t in intl_terms if t in activity_text)
    points += min(intl_hits, 3)

    # Check grant portfolio composition
    grants = conn.execute(
        "SELECT grantee_name, purpose, is_foreign "
        "FROM grants WHERE ein = ?",
        (ein,),
    ).fetchall()

    if grants:
        faith_grants = 0
        for name, purpose, is_foreign in grants:
            combined = f"{name} {purpose}".lower()
            if any(t in combined for t in faith_terms + intl_terms):
                faith_grants += 1

        # >50% faith/intl grants: +3 pts
        if faith_grants / len(grants) > 0.5:
            points += 3

    cap = SCORE_WEIGHTS['focus_area']
    return min(points, cap)


def score_opportunity(alignment_score, grant_amount):
    """
    Calculate Opportunity Score (1-100).
    60% Alignment Score + 40% Grant Amount.
    """
    # Alignment component (60%)
    alignment_pts = (alignment_score / 100) * 60

    # Grant amount component (0-40 pts)
    grant_pts = 0
    try:
        amt = float(grant_amount) if grant_amount else 0
    except (ValueError, TypeError):
        amt = 0

    if amt >= 100_000:
        grant_pts = 40
    elif amt >= 50_000:
        grant_pts = 33
    elif amt >= 25_000:
        grant_pts = 26
    elif amt >= 10_000:
        grant_pts = 20
    elif amt >= 5_000:
        grant_pts = 13
    elif amt >= 1_000:
        grant_pts = 7

    return min(int(alignment_pts + grant_pts), 100)


def score_foundation(conn, ein, target_lookup):
    """Calculate total 1-100 alignment score for a foundation."""
    grantee_pts, grantee_list, grantee_count = score_grantee_matches(
        conn, ein, target_lookup
    )
    keyword_pts, keyword_list, keyword_count = score_keywords(
        conn, ein
    )
    intl_pts, gives_intl = score_international(conn, ein)
    focus_pts = score_focus_area(conn, ein)

    total = min(
        grantee_pts + keyword_pts + intl_pts + focus_pts, 100
    )

    return {
        'alignment_score': total,
        'grantee_matches': '; '.join(grantee_list),
        'grantee_match_count': grantee_count,
        'keyword_matches': '; '.join(keyword_list),
        'keyword_match_count': keyword_count,
        'gives_internationally': 'Yes' if gives_intl else 'No',
    }


def run():
    """Main scoring pipeline."""
    from src.downloader import load_matches_csv

    matches_df = load_matches_csv()
    conn = sqlite3.connect(DB_PATH)
    target_lookup = build_target_lookup()
    candidates = build_foundation_candidates(conn)

    log.info("Scoring %d foundations against %d DB entries...",
             len(matches_df), len(candidates))

    results = []
    unmatched = []

    for i, (_, row) in enumerate(matches_df.iterrows()):
        if i % 500 == 0 and i > 0:
            log.info("Scored %d / %d...", i, len(matches_df))

        name = str(row['foundation_name'])
        city = str(row.get('city', ''))
        state = str(row.get('state', ''))

        # Find this foundation in our DB
        match, score, pass_num = find_match(
            name, city, state, candidates
        )

        result = {
            'foundation_name': name,
            'city': city,
            'state': state,
            'saved': row.get('saved', ''),
            'hidden': row.get('hidden', ''),
            'match_percent': row.get('match_percent', ''),
            'grant_amount': row.get('grant_amount', ''),
        }

        grant_amount = row.get('grant_amount', '')

        if match and pass_num > 0:
            ein = match['ein']
            scores = score_foundation(conn, ein, target_lookup)
            opp_score = score_opportunity(
                scores['alignment_score'], grant_amount
            )
            result.update({
                'ein': ein,
                'data_found': 'Yes',
                'opportunity_score': opp_score,
                **scores,
            })
        else:
            opp_score = score_opportunity(0, grant_amount)
            result.update({
                'ein': '',
                'data_found': 'No',
                'alignment_score': 0,
                'opportunity_score': opp_score,
                'grantee_matches': '',
                'grantee_match_count': 0,
                'keyword_matches': '',
                'keyword_match_count': 0,
                'gives_internationally': '',
            })
            unmatched.append({
                'name': name,
                'city': city,
                'state': state,
                'best_candidate': match['name'] if match else '',
                'best_score': score,
            })

        results.append(result)

    # Write results
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(
        'opportunity_score', ascending=False
    )
    results_df.to_csv('results.csv', index=False, quoting=1)
    log.info("Wrote %d rows to results.csv", len(results_df))

    # Write unmatched
    if unmatched:
        unmatched_df = pd.DataFrame(unmatched)
        unmatched_df.to_csv('unmatched.csv', index=False)
        log.info("Wrote %d unmatched to unmatched.csv",
                 len(unmatched_df))

    # Summary stats
    aligned = results_df[results_df['alignment_score'] > 0]
    log.info(
        "Summary: %d aligned > 0, avg alignment %.1f, "
        "max alignment %d, avg opportunity %.1f, "
        "max opportunity %d, %d with data found",
        len(aligned),
        aligned['alignment_score'].mean() if len(aligned) > 0 else 0,
        results_df['alignment_score'].max(),
        results_df['opportunity_score'].mean(),
        results_df['opportunity_score'].max(),
        len(results_df[results_df['data_found'] == 'Yes']),
    )

    conn.close()


if __name__ == '__main__':
    run()
