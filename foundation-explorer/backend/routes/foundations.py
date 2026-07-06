"""Foundations endpoints: list, stats, detail, grants, recipients."""

import json

from fastapi import APIRouter, Depends, HTTPException

from db import get_conn, rows_to_dicts
from models import FoundationFilters, foundation_filters_dep
from queries import foundation_filters, order_clause

router = APIRouter(prefix='/api/foundations', tags=['foundations'])

LIST_COLS = (
    'ein, foundation_name, city, state, distributions, assets, revenue, '
    'faith_alignment_score, faith_score_composite, christian_giving_pct, '
    'christian_dollars_3yr, total_giving, faith_tier, application_status, '
    'is_testamentary_trust, is_small_fund, data_found, propublica_url, '
    'latest_tax_year'
)


@router.get('')
def list_foundations(
    p: FoundationFilters = Depends(foundation_filters_dep),
):
    where, args = foundation_filters(p)
    order = order_clause(p)
    offset = (p.page - 1) * p.page_size
    conn = get_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM universe WHERE {where}", args
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT {LIST_COLS} FROM universe WHERE {where} "
            f"{order} LIMIT ? OFFSET ?",
            args + [p.page_size, offset],
        ).fetchall()
    finally:
        conn.close()
    return {
        'total': total,
        'page': p.page,
        'page_size': p.page_size,
        'rows': rows_to_dicts(rows),
    }


@router.get('/stats')
def foundation_stats():
    conn = get_conn()
    try:
        row = conn.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN data_found = 'Yes' THEN 1 ELSE 0 END)
                       AS with_filings,
                   SUM(CASE WHEN faith_alignment_score IS NOT NULL
                       THEN 1 ELSE 0 END) AS scored,
                   SUM(CASE WHEN faith_score_composite >= 60
                       THEN 1 ELSE 0 END) AS high_alignment,
                   SUM(CASE WHEN application_status =
                       'Accepting Applications'
                       AND faith_score_composite > 30
                       AND christian_dollars_3yr >= 100000
                       AND (is_testamentary_trust = 0
                            OR is_testamentary_trust IS NULL)
                       THEN 1 ELSE 0 END) AS best_prospects,
                   SUM(CASE WHEN application_status =
                       'Accepting Applications'
                       AND faith_score_composite > 30
                       AND christian_dollars_3yr >= 100000
                       AND (is_testamentary_trust = 0
                            OR is_testamentary_trust IS NULL)
                       THEN christian_dollars_3yr ELSE 0 END)
                       AS best_prospect_dollars,
                   SUM(is_testamentary_trust) AS testamentary_trusts,
                   SUM(is_small_fund) AS small_funds,
                   SUM(christian_dollars_3yr) AS christian_dollars_total,
                   SUM(CASE WHEN application_status =
                       'Accepting Applications' THEN 1 ELSE 0 END)
                       AS accepting,
                   SUM(CASE WHEN application_status = 'Invite Only'
                       THEN 1 ELSE 0 END) AS invite_only,
                   SUM(CASE WHEN website != '' AND website IS NOT NULL
                       THEN 1 ELSE 0 END) AS with_website,
                   SUM(CASE WHEN phone != '' AND phone IS NOT NULL
                       THEN 1 ELSE 0 END) AS with_phone,
                   SUM(CASE WHEN contact_person != ''
                       AND contact_person IS NOT NULL THEN 1 ELSE 0 END)
                       AS with_contact,
                   SUM(total_giving) AS total_grant_dollars,
                   SUM(faith_giving) AS faith_grant_dollars
            FROM universe
        """).fetchone()
        grants = conn.execute(
            "SELECT COUNT(*), SUM(amount) FROM pipeline.grants"
        ).fetchone()
    finally:
        conn.close()
    out = dict(row)
    out['total_grants'] = grants[0]
    out['total_grants_dollars'] = grants[1]
    return out


@router.get('/{ein}')
def foundation_detail(ein: str):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM universe WHERE ein = ?", (ein,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, 'Foundation not found')
        detail = dict(row)
        filings = conn.execute(
            "SELECT * FROM pipeline.foundations WHERE ein IN (?, ?) "
            "ORDER BY tax_year DESC",
            (ein, ein.lstrip('0')),
        ).fetchall()
        detail['filings'] = rows_to_dicts(filings)
        acts = conn.execute(
            "SELECT description, expenses, tax_year "
            "FROM pipeline.charitable_activities WHERE ein IN (?, ?) "
            "ORDER BY tax_year DESC, expenses DESC LIMIT 100",
            (ein, ein.lstrip('0')),
        ).fetchall()
        detail['activities'] = rows_to_dicts(acts)
    finally:
        conn.close()
    return detail


@router.get('/{ein}/grants')
def foundation_grants(ein: str, page: int = 1, page_size: int = 50,
                      q: str | None = None):
    where = "ein IN (?, ?)"
    args = [ein, ein.lstrip('0')]
    if q:
        where += " AND (grantee_name LIKE ? OR purpose LIKE ?)"
        args += [f'%{q}%', f'%{q}%']
    offset = (max(1, page) - 1) * page_size
    conn = get_conn()
    try:
        total, dollars = conn.execute(
            f"SELECT COUNT(*), SUM(amount) FROM pipeline.grants "
            f"WHERE {where}", args
        ).fetchone()
        rows = conn.execute(
            f"SELECT grantee_name, city, state, country, is_foreign, "
            f"amount, purpose, tax_year FROM pipeline.grants "
            f"WHERE {where} ORDER BY amount DESC LIMIT ? OFFSET ?",
            args + [min(page_size, 250), offset],
        ).fetchall()
    finally:
        conn.close()
    return {'total': total, 'total_dollars': dollars,
            'rows': rows_to_dicts(rows)}


@router.get('/{ein}/recipients')
def foundation_recipients(ein: str, limit: int = 20):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT grantee_name, COUNT(*) AS grant_count, "
            "SUM(amount) AS total_amount, "
            "COUNT(DISTINCT tax_year) AS years "
            "FROM pipeline.grants WHERE ein IN (?, ?) "
            "GROUP BY grantee_name ORDER BY total_amount DESC LIMIT ?",
            (ein, ein.lstrip('0'), min(limit, 100)),
        ).fetchall()
        distinct = conn.execute(
            "SELECT COUNT(DISTINCT grantee_name) FROM pipeline.grants "
            "WHERE ein IN (?, ?)", (ein, ein.lstrip('0')),
        ).fetchone()[0]
        out = rows_to_dicts(rows)
        # attach tags from the knowledge base where present
        for r in out:
            tag_row = conn.execute(
                "SELECT tags FROM pipeline.recipients "
                "WHERE display_name = ? LIMIT 1", (r['grantee_name'],),
            ).fetchone()
            r['tags'] = json.loads(tag_row[0]) if tag_row else []
    finally:
        conn.close()
    return {'distinct_recipients': distinct, 'top': out}
