"""Analytics + data-quality endpoints."""

from fastapi import APIRouter

from db import get_conn, rows_to_dicts

router = APIRouter(prefix='/api/analytics', tags=['analytics'])


@router.get('/score-distribution')
def score_distribution():
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT CAST(faith_alignment_score / 5 AS INT) * 5 AS bucket,
                   COUNT(*) AS n
            FROM universe WHERE faith_alignment_score IS NOT NULL
            GROUP BY bucket ORDER BY bucket
        """).fetchall()
    finally:
        conn.close()
    return rows_to_dicts(rows)


@router.get('/size-distribution')
def size_distribution():
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT CASE
                WHEN distributions < 10000 THEN '<$10k'
                WHEN distributions < 100000 THEN '$10k-100k'
                WHEN distributions < 1000000 THEN '$100k-1M'
                WHEN distributions < 10000000 THEN '$1M-10M'
                WHEN distributions < 100000000 THEN '$10M-100M'
                ELSE '$100M+' END AS bucket,
                COUNT(*) AS n
            FROM universe WHERE distributions IS NOT NULL
            GROUP BY bucket
        """).fetchall()
    finally:
        conn.close()
    order = ['<$10k', '$10k-100k', '$100k-1M', '$1M-10M',
             '$10M-100M', '$100M+']
    data = {r['bucket']: r['n'] for r in rows}
    return [{'bucket': b, 'n': data.get(b, 0)} for b in order]


@router.get('/state-breakdown')
def state_breakdown():
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT state, COUNT(*) AS foundations,
                   SUM(distributions) AS distributions,
                   AVG(faith_alignment_score) AS avg_score,
                   SUM(CASE WHEN faith_alignment_score >= 40
                       THEN 1 ELSE 0 END) AS faith_funders
            FROM universe WHERE state != '' AND state IS NOT NULL
            GROUP BY state ORDER BY foundations DESC
        """).fetchall()
    finally:
        conn.close()
    return rows_to_dicts(rows)


@router.get('/top-funders')
def top_funders(limit: int = 100):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ein, foundation_name, city, state, "
            "faith_alignment_score, faith_tier, christian_giving_pct, "
            "faith_giving, total_giving, application_status "
            "FROM universe WHERE faith_alignment_score IS NOT NULL "
            "ORDER BY faith_alignment_score DESC, faith_giving DESC "
            "LIMIT ?", (min(limit, 500),),
        ).fetchall()
    finally:
        conn.close()
    return rows_to_dicts(rows)


@router.get('/yearly-trends')
def yearly_trends():
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT tax_year, COUNT(*) AS grants, SUM(amount) AS dollars
            FROM pipeline.grants WHERE tax_year >= 2021
            GROUP BY tax_year ORDER BY tax_year
        """).fetchall()
    finally:
        conn.close()
    return rows_to_dicts(rows)


@router.get('/data-quality')
def data_quality():
    conn = get_conn()
    try:
        u = conn.execute("""
            SELECT COUNT(*) AS total,
                SUM(CASE WHEN data_found='Yes' THEN 1 ELSE 0 END)
                    AS with_filings,
                SUM(CASE WHEN phone != '' AND phone IS NOT NULL
                    THEN 1 ELSE 0 END) AS with_phone,
                SUM(CASE WHEN website != '' AND website IS NOT NULL
                    THEN 1 ELSE 0 END) AS with_website,
                SUM(CASE WHEN contact_email != ''
                    AND contact_email IS NOT NULL THEN 1 ELSE 0 END)
                    AS with_email,
                SUM(CASE WHEN contact_person != ''
                    AND contact_person IS NOT NULL THEN 1 ELSE 0 END)
                    AS with_contact,
                SUM(CASE WHEN revenue IS NOT NULL THEN 1 ELSE 0 END)
                    AS with_revenue,
                SUM(CASE WHEN application_status != ''
                    AND application_status IS NOT NULL THEN 1 ELSE 0 END)
                    AS with_status,
                SUM(CASE WHEN faith_alignment_score IS NOT NULL
                    THEN 1 ELSE 0 END) AS scored,
                SUM(CASE WHEN states_given_to != ''
                    AND states_given_to IS NOT NULL THEN 1 ELSE 0 END)
                    AS with_states
            FROM universe
        """).fetchone()
        pipeline = conn.execute("""
            SELECT (SELECT COUNT(*) FROM pipeline.foundations),
                   (SELECT COUNT(*) FROM pipeline.grants),
                   (SELECT SUM(amount) FROM pipeline.grants),
                   (SELECT COUNT(*) FROM pipeline.recipients),
                   (SELECT COUNT(*) FROM pipeline.recipients
                    WHERE source = 'pending' AND max_grant >= 5000),
                   (SELECT COUNT(*) FROM pipeline.recipients
                    WHERE source IN ('rule', 'seed', 'llm'))
        """).fetchone()
    finally:
        conn.close()
    return {
        'universe': dict(u),
        'pipeline': {
            'foundation_filings': pipeline[0],
            'grants': pipeline[1],
            'grant_dollars': pipeline[2],
            'recipients': pipeline[3],
            'recipients_pending_llm_5k': pipeline[4],
            'recipients_tagged': pipeline[5],
        },
    }
