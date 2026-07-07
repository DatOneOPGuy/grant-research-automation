"""Generate static demo JSON for the Netlify demo build.

Sample: top 1,500 foundations by faith score + 500 random others.
Aggregates (stats/analytics) are computed over the FULL database so the
demo's headline numbers are real; only the browsable rows are sampled.
Output: frontend/public/demo/
"""

import json
from pathlib import Path

from db import get_conn, rows_to_dicts

OUT = Path(__file__).resolve().parent.parent / 'frontend' / 'public' / 'demo'
GRANTS_PER_FOUNDATION = 25


def dump(name: str, data):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, default=str))
    if name in ('foundations.json', 'analytics.json', 'stats.json'):
        print(f"  {name}: {path.stat().st_size / 1024:.0f} KB")


def christian_evidence(conn, ein, bare):
    """Christian recipients for one foundation (matches the API endpoint)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.classifier import tradition
    from src.faith_config import CONFIDENCE_MIN, FAITH_TAGS
    from src.matcher import normalize
    faith = set(FAITH_TAGS)
    agg = {}
    for gname, amount, year in conn.execute(
        "SELECT grantee_name, amount, tax_year FROM pipeline.grants "
        "WHERE ein IN (?, ?) AND grantee_name != '' "
        "AND tax_year IN (2023, 2024, 2025)", (ein, bare)):
        norm = normalize(gname)
        if norm not in agg:
            tag = conn.execute(
                "SELECT tags FROM pipeline.recipients WHERE name_norm = ?",
                (norm,)).fetchone()
            names = ({t['name'] for t in json.loads(tag[0])
                      if t.get('confidence', 0) >= CONFIDENCE_MIN}
                     if tag else set())
            agg[norm] = {'is_christian': bool(names & faith), 'name': gname,
                         'total': 0, 'recent': 0, 'tradition': tradition(gname)}
        e = agg[norm]
        if e['is_christian']:
            e['total'] += amount or 0
            e['recent'] = max(e['recent'], year)
    return sorted(
        ({'name': e['name'], 'total': e['total'],
          'most_recent_year': e['recent'], 'tradition': e['tradition']}
         for e in agg.values() if e['is_christian'] and e['total'] > 0),
        key=lambda x: -x['total'])[:30]


# Marquee foundations that must be searchable in the demo regardless of
# where they rank (Part 10 test set + verification set).
MARQUEE_EINS = [
    '626041468',  # Maclellan
    '350868122',  # Lilly Endowment
    '621322826',  # John Templeton
    '237456468',  # M J Murdock
    '916020515',  # Stewardship
    '205132900',  # The Rees-Jones Foundation
    '830590263',  # Mother Cabrini Health Foundation
]
MARQUEE_NAMES = ['MACLELLAN', 'LILLY ENDOWMENT', 'TEMPLETON FOUNDATION',
                 'MURDOCK CHARITABLE', 'STEWARDSHIP FOUNDATION',
                 'REES-JONES', 'CABRINI HEALTH']


def sample_eins(conn) -> list[str]:
    # rank by the corrected composite score
    top = [r[0] for r in conn.execute(
        "SELECT ein FROM universe WHERE christian_dollars_3yr > 0 "
        "ORDER BY christian_dollars_3yr DESC "
        "LIMIT 1500"
    )]
    # top Christian-dollar givers
    vol = [r[0] for r in conn.execute(
        "SELECT ein FROM universe WHERE christian_dollars_3yr > 0 "
        "ORDER BY christian_dollars_3yr DESC LIMIT 200"
    )]
    # force-include marquee foundations by EIN and by name
    marquee = set(MARQUEE_EINS)
    for pat in MARQUEE_NAMES:
        marquee.update(r[0] for r in conn.execute(
            "SELECT ein FROM universe WHERE foundation_name LIKE ?",
            (f'%{pat}%',)))
    seen = set(top) | set(vol) | marquee
    rand = [r[0] for r in conn.execute(
        "SELECT ein FROM universe WHERE ein NOT IN "
        f"({','.join('?' * len(seen))}) ORDER BY ein LIMIT 500", list(seen)
    )]
    ordered = list(dict.fromkeys(top + vol + sorted(marquee) + rand))
    return ordered


def main():
    conn = get_conn()
    eins = sample_eins(conn)
    marks = ','.join('?' * len(eins))

    rows = rows_to_dicts(conn.execute(
        f"SELECT * FROM universe WHERE ein IN ({marks})", eins
    ).fetchall())
    dump('foundations.json', rows)

    # per-foundation detail bundles
    for ein in eins:
        bare = ein.lstrip('0')
        grants = rows_to_dicts(conn.execute(
            "SELECT grantee_name, city, state, country, is_foreign, "
            "amount, purpose, tax_year FROM pipeline.grants "
            "WHERE ein IN (?, ?) ORDER BY amount DESC LIMIT ?",
            (ein, bare, GRANTS_PER_FOUNDATION),
        ).fetchall())
        totals = conn.execute(
            "SELECT COUNT(*), SUM(amount) FROM pipeline.grants "
            "WHERE ein IN (?, ?)", (ein, bare),
        ).fetchone()
        recipients = rows_to_dicts(conn.execute(
            "SELECT grantee_name, COUNT(*) AS grant_count, "
            "SUM(amount) AS total_amount, "
            "COUNT(DISTINCT tax_year) AS years FROM pipeline.grants "
            "WHERE ein IN (?, ?) GROUP BY grantee_name "
            "ORDER BY total_amount DESC LIMIT 20", (ein, bare),
        ).fetchall())
        for r in recipients:
            tag_row = conn.execute(
                "SELECT tags FROM pipeline.recipients "
                "WHERE display_name = ? LIMIT 1", (r['grantee_name'],),
            ).fetchone()
            r['tags'] = json.loads(tag_row[0]) if tag_row else []
        acts = rows_to_dicts(conn.execute(
            "SELECT description, expenses, tax_year "
            "FROM pipeline.charitable_activities WHERE ein IN (?, ?) "
            "ORDER BY tax_year DESC, expenses DESC LIMIT 10",
            (ein, bare),
        ).fetchall())
        dump(f'f/{ein}.json', {
            'grants': grants, 'grants_total': totals[0],
            'grants_dollars': totals[1],
            'recipients': recipients, 'activities': acts,
            'christian_evidence': christian_evidence(conn, ein, bare),
        })

    # flat samples for the Grants and Recipients pages
    bare_eins = [e.lstrip('0') for e in eins]
    all_marks = ','.join('?' * (len(eins) * 2))
    grants_sample = rows_to_dicts(conn.execute(
        f"SELECT g.ein, g.grantee_name, g.city, g.state, g.country, "
        f"g.is_foreign, g.amount, g.purpose, g.tax_year "
        f"FROM pipeline.grants g WHERE g.ein IN ({all_marks}) "
        f"ORDER BY g.amount DESC LIMIT 5000", eins + bare_eins,
    ).fetchall())
    names = dict(conn.execute(
        f"SELECT ein, foundation_name FROM universe WHERE ein IN ({marks})",
        eins,
    ).fetchall())
    for g in grants_sample:
        g['foundation_name'] = names.get(str(g['ein']).zfill(9), '')
    dump('grants.json', grants_sample)

    recips = rows_to_dicts(conn.execute(
        "SELECT name_norm, display_name, tags, source, max_grant "
        "FROM pipeline.recipients WHERE tags != '[]' "
        "ORDER BY max_grant DESC LIMIT 3000"
    ).fetchall())
    for r in recips:
        r['tags'] = json.loads(r['tags'] or '[]')
    dump('recipients.json', recips)

    # full-database aggregates (real numbers)
    from routes.analytics import (
        data_quality, leaderboards, score_distribution, size_distribution,
        state_breakdown, state_christian, top_funders, verification,
        yearly_trends,
    )
    from routes.foundations import foundation_stats
    dump('stats.json', foundation_stats())
    dump('analytics.json', {
        'score-distribution': score_distribution(),
        'size-distribution': size_distribution(),
        'state-breakdown': state_breakdown(),
        'state-christian': state_christian(),
        'top-funders': top_funders(100),
        'yearly-trends': yearly_trends(),
        'data-quality': data_quality(),
        'verification': verification(),
        'leaderboards': leaderboards(10),
    })
    conn.close()
    print(f"Demo data written to {OUT} ({len(eins)} foundations)")


if __name__ == '__main__':
    main()
