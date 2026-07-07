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


COVERAGE_DISPLAY_THRESHOLD = 85  # >= this coverage -> show a single %


def load_tag_status(conn) -> dict[str, str]:
    """name_norm -> 'christian' | 'nonchristian' (untagged names omitted)."""
    status = {}
    for norm, tags_json in conn.execute(
        "SELECT name_norm, tags FROM recipients WHERE tags != '[]'"
    ):
        names = {t['name'] for t in json.loads(tags_json)
                 if t.get('confidence', 0) >= CONFIDENCE_MIN}
        if not names:
            continue
        status[norm] = 'christian' if names & FAITH_TAG_SET else 'nonchristian'
    return status


def ensure_table(conn):
    conn.execute("DROP TABLE IF EXISTS foundation_enrich")
    conn.execute("""
        CREATE TABLE foundation_enrich (
            ein TEXT PRIMARY KEY,
            christian_dollars_2023 INTEGER, christian_dollars_2024 INTEGER,
            christian_dollars_2025 INTEGER, christian_dollars_3yr INTEGER,
            christian_grant_count_3yr INTEGER, total_giving_3yr INTEGER,
            nonchristian_dollars_3yr INTEGER, unclassified_dollars_3yr INTEGER,
            classification_coverage INTEGER,
            christian_pct_floor INTEGER, christian_pct_ceiling INTEGER,
            christian_pct_display TEXT,
            verdict TEXT, christian_recipient_count INTEGER,
            most_recent_christian_year INTEGER, christian_preview TEXT,
            predominant_tradition TEXT, typical_grant_size INTEGER,
            largest_christian_grant INTEGER,
            faith_score_pct INTEGER, faith_score_composite INTEGER,
            volume_component INTEGER,
            is_testamentary_trust INTEGER, is_small_fund INTEGER,
            is_actively_giving INTEGER
        )
    """)


# Verdict thresholds (confirmed Christian giving, 3-year window)
VERDICT_MIN_DOLLARS = 100_000
VERDICT_MIN_RECIPIENTS = 3


def _median(vals: list) -> int:
    if not vals:
        return 0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    return int(s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2)


def predominant_tradition(recipients: dict) -> str:
    """recipients: norm -> [total$, year, name]. Returns the tradition with
    >50% of confirmed Christian dollars, else 'Mixed'."""
    from src.classifier import tradition
    sums = defaultdict(int)
    total = 0
    for tot, _yr, name in recipients.values():
        if tot <= 0:
            continue
        total += tot
        sums[tradition(name) or 'Other'] += tot
    if total <= 0:
        return ''
    for trad in ('Catholic', 'Evangelical/Protestant', 'Orthodox'):
        if sums.get(trad, 0) > 0.5 * total:
            return trad
    return 'Mixed'


def verdict_for(christian_dollars: int, recipient_count: int) -> str:
    if recipient_count == 0 or christian_dollars <= 0:
        return 'No confirmed Christian giving'
    if (christian_dollars >= VERDICT_MIN_DOLLARS
            and recipient_count >= VERDICT_MIN_RECIPIENTS):
        return 'Funds Christian organizations'
    return 'Some Christian giving'


def composite(pct: float, christian_dollars: int) -> tuple[int, int]:
    """Return (composite_score, volume_component)."""
    vol = 0.0
    if christian_dollars > 0:
        vol = (math.log10(christian_dollars + 1)
               / math.log10(VOLUME_CAP)) * 100
        vol = max(0.0, min(100.0, vol))
    comp = 0.4 * max(0.0, min(100.0, pct)) + 0.6 * vol
    return round(min(100.0, comp)), round(vol)


def _display(floor, ceiling, coverage):
    """Honest percentage string: single value if well-covered, else range."""
    if coverage >= COVERAGE_DISPLAY_THRESHOLD:
        return f"{floor}% Christian"
    return (f"{floor}–{ceiling}% Christian "
            f"({coverage}% of grants classified)")


def run():
    conn = sqlite3.connect(DB_PATH)
    status = load_tag_status(conn)
    log.info("Classified recipients: %d", len(status))

    # accumulate per EIN over the 2023-2025 window
    cd_year = defaultdict(lambda: defaultdict(int))   # ein -> year -> $
    cd_total = defaultdict(int)
    cd_count = defaultdict(int)
    nonchr = defaultdict(int)
    unclass = defaultdict(int)
    tot = defaultdict(int)
    # per-foundation Christian-recipient evidence: ein -> recip_norm ->
    # [total$, max_year, display_name]
    evidence = defaultdict(dict)
    recent_year = defaultdict(int)
    cd_amounts = defaultdict(list)  # ein -> list of Christian grant amounts
    for ein, name, amount, year in conn.execute(
        "SELECT ein, grantee_name, amount, tax_year FROM grants "
        "WHERE grantee_name != ''"
    ):
        ein = ein.zfill(9)
        amount = amount or 0
        if year not in (2023, 2024, 2025):
            continue
        tot[ein] += amount
        norm = normalize(name)
        st = status.get(norm)
        if st == 'christian':
            cd_total[ein] += amount
            cd_year[ein][year] += amount
            if amount > 0:
                cd_amounts[ein].append(amount)
            ev = evidence[ein].get(norm)
            if ev is None:
                evidence[ein][norm] = [amount, year, name]
            else:
                ev[0] += amount
                ev[1] = max(ev[1], year)
            if year > recent_year[ein]:
                recent_year[ein] = year
        elif st == 'nonchristian':
            nonchr[ein] += amount
        else:
            unclass[ein] += amount
    for ein, recips in evidence.items():
        cd_count[ein] = len(recips)
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
        # clamp buckets to >= 0 (some 990-PF grants carry negative
        # correction amounts that would otherwise break the ratios)
        cdt = max(0, cd_total.get(ein, 0))
        ncr = max(0, nonchr.get(ein, 0))
        unc = max(0, unclass.get(ein, 0))
        denom = max(total3, cdt + ncr + unc, 1)
        pct = 100 * cdt / denom
        floor = min(100, max(0, round(pct)))
        coverage = min(100, max(0, round(100 * (cdt + ncr) / denom)))
        ceiling = min(100, max(floor, round(100 * (cdt + unc) / denom)))
        display = _display(floor, ceiling, coverage) if total3 > 0 else ''
        comp, vol = composite(pct, cdt)
        nm = names.get(ein, '')
        # verdict + evidence preview
        rcount = cd_count.get(ein, 0)
        verdict = verdict_for(cdt, rcount)
        preview = ''
        trad = ''
        if evidence.get(ein):
            top = sorted(evidence[ein].values(), key=lambda e: -e[0])
            top_names = [t[2] for t in top[:2]]
            more = rcount - len(top_names)
            preview = ', '.join(top_names)
            if more > 0:
                preview += f', +{more} more'
            trad = predominant_tradition(evidence[ein])
        amounts = cd_amounts.get(ein, [])
        typical = _median(amounts)
        largest = max(amounts) if amounts else 0
        conn.execute(
            "INSERT OR REPLACE INTO foundation_enrich VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ein,
             cd_year[ein].get(2023, 0), cd_year[ein].get(2024, 0),
             cd_year[ein].get(2025, 0), cdt, rcount, total3,
             ncr, unc, coverage, floor, ceiling, display,
             verdict, rcount, recent_year.get(ein) or None, preview,
             trad, typical, largest,
             round(pct), comp, vol,
             1 if TRUST_RE.search(nm) else 0,
             small.get(ein, 0), active.get(ein, 0)),
        )
        written += 1
    conn.commit()

    stats = conn.execute(
        "SELECT SUM(is_testamentary_trust), SUM(is_small_fund), "
        "SUM(CASE WHEN classification_coverage >= 85 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN christian_dollars_3yr > 0 THEN 1 ELSE 0 END) "
        "FROM foundation_enrich"
    ).fetchone()
    conn.close()
    log.info("Wrote %d enrich rows. Testamentary=%s, small=%s, "
             "coverage>=85%%=%s, any-christian-giving=%s",
             written, *stats)


if __name__ == '__main__':
    run()
