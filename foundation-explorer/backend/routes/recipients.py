"""Recipients explorer over the knowledge-base table (1.05M rows)."""

import json

from fastapi import APIRouter, Query

from db import get_conn, rows_to_dicts

router = APIRouter(prefix='/api/recipients', tags=['recipients'])


@router.get('')
def list_recipients(
    q: str | None = None,
    tag: str | None = None,
    source: str | None = None,
    min_max_grant: int | None = None,
    page: int = 1,
    page_size: int = Query(default=50, le=250),
):
    where, args = ['1=1'], []
    if q:
        where.append('display_name LIKE ?')
        args.append(f'%{q}%')
    if tag:
        where.append("tags LIKE ?")
        args.append(f'%"{tag}"%')
    if source:
        where.append('source = ?')
        args.append(source)
    if min_max_grant is not None:
        where.append('max_grant >= ?')
        args.append(min_max_grant)
    clause = ' AND '.join(where)
    offset = (max(1, page) - 1) * page_size
    conn = get_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM pipeline.recipients WHERE {clause}",
            args,
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT name_norm, display_name, tags, source, max_grant "
            f"FROM pipeline.recipients WHERE {clause} "
            f"ORDER BY max_grant DESC LIMIT ? OFFSET ?",
            args + [page_size, offset],
        ).fetchall()
    finally:
        conn.close()
    out = rows_to_dicts(rows)
    for r in out:
        r['tags'] = json.loads(r['tags'] or '[]')
    return {'total': total, 'page': page, 'rows': out}


@router.get('/stats')
def recipient_stats():
    conn = get_conn()
    try:
        by_source = conn.execute(
            "SELECT source, COUNT(*) FROM pipeline.recipients "
            "GROUP BY source"
        ).fetchall()
    finally:
        conn.close()
    return {'by_source': dict(by_source)}


@router.get('/{name_norm}/funders')
def recipient_funders(name_norm: str, limit: int = 50):
    conn = get_conn()
    try:
        display = conn.execute(
            "SELECT display_name FROM pipeline.recipients "
            "WHERE name_norm = ?", (name_norm,),
        ).fetchone()
        if not display:
            return {'funders': []}
        rows = conn.execute(
            "SELECT g.ein, COUNT(*) AS n, SUM(g.amount) AS dollars, "
            "GROUP_CONCAT(DISTINCT g.tax_year) AS years "
            "FROM pipeline.grants g WHERE g.grantee_name = ? "
            "GROUP BY g.ein ORDER BY dollars DESC LIMIT ?",
            (display[0], min(limit, 200)),
        ).fetchall()
        out = rows_to_dicts(rows)
        eins = {str(r['ein']).zfill(9) for r in out}
        if eins:
            marks = ','.join('?' * len(eins))
            names = dict(conn.execute(
                f"SELECT ein, foundation_name FROM universe "
                f"WHERE ein IN ({marks})", list(eins)
            ).fetchall())
            for r in out:
                r['foundation_name'] = names.get(
                    str(r['ein']).zfill(9), '')
    finally:
        conn.close()
    return {'funders': out}
