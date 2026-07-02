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
    print(f"  {name}: {path.stat().st_size / 1024:.0f} KB")


def sample_eins(conn) -> list[str]:
    top = [r[0] for r in conn.execute(
        "SELECT ein FROM universe WHERE faith_alignment_score IS NOT NULL "
        "ORDER BY faith_alignment_score DESC, faith_giving DESC LIMIT 1500"
    )]
    rand = [r[0] for r in conn.execute(
        "SELECT ein FROM universe WHERE ein NOT IN "
        f"({','.join('?' * len(top))}) ORDER BY ein LIMIT 500", top
    )]
    return top + rand


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
        data_quality, score_distribution, size_distribution,
        state_breakdown, top_funders, yearly_trends,
    )
    from routes.foundations import foundation_stats
    dump('stats.json', foundation_stats())
    dump('analytics.json', {
        'score-distribution': score_distribution(),
        'size-distribution': size_distribution(),
        'state-breakdown': state_breakdown(),
        'top-funders': top_funders(100),
        'yearly-trends': yearly_trends(),
        'data-quality': data_quality(),
    })
    conn.close()
    print(f"Demo data written to {OUT} ({len(eins)} foundations)")


if __name__ == '__main__':
    main()
