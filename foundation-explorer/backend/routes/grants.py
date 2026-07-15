"""Grants explorer endpoints over the 5M-row pipeline grants table."""

from db import get_conn, rows_to_dicts
from fastapi import APIRouter, Query

router = APIRouter(prefix='/api/grants', tags=['grants'])
DATA_YEARS = (2023, 2024)


def _filters(q, years, recipient_state, foundation_state, amount_min,
             amount_max, foreign_only):
    where, args = ['1=1'], []
    if q:
        where.append('(g.grantee_name LIKE ? OR g.purpose LIKE ?)')
        args += [f'%{q}%', f'%{q}%']
    selected_years = years or list(DATA_YEARS)
    if selected_years:
        marks = ','.join('?' * len(selected_years))
        where.append(f'g.tax_year IN ({marks})')
        args += selected_years
    if recipient_state:
        where.append('g.state = ?')
        args.append(recipient_state)
    if amount_min is not None:
        where.append('g.amount >= ?')
        args.append(amount_min)
    if amount_max is not None:
        where.append('g.amount <= ?')
        args.append(amount_max)
    if foreign_only:
        where.append('g.is_foreign = 1')
    join = ''
    if foundation_state:
        join = ('JOIN universe u ON u.ein = printf("%09d", g.ein) '
                'AND u.state = ?')
        args.insert(0, foundation_state)
    return ' AND '.join(where), args, join


@router.get('')
def list_grants(
    q: str | None = None,
    years: list[int] = Query(default=[]),
    recipient_state: str | None = None,
    foundation_state: str | None = None,
    amount_min: int | None = None,
    amount_max: int | None = None,
    foreign_only: bool = False,
    page: int = 1,
    page_size: int = Query(default=50, le=250),
):
    where, args, join = _filters(q, years, recipient_state,
                                 foundation_state, amount_min,
                                 amount_max, foreign_only)
    offset = (max(1, page) - 1) * page_size
    conn = get_conn()
    try:
        total, dollars = conn.execute(
            f"SELECT COUNT(*), SUM(g.amount) FROM pipeline.grants g "
            f"{join} WHERE {where}", args
        ).fetchone()
        rows = conn.execute(
            f"SELECT g.ein, g.grantee_name, g.city, g.state, g.country, "
            f"g.is_foreign, g.amount, g.purpose, g.tax_year "
            f"FROM pipeline.grants g {join} WHERE {where} "
            f"ORDER BY g.amount DESC LIMIT ? OFFSET ?",
            args + [page_size, offset],
        ).fetchall()
        out = rows_to_dicts(rows)
        # resolve funder names in one pass
        eins = {str(r['ein']).zfill(9) for r in out}
        if eins:
            marks = ','.join('?' * len(eins))
            names = dict(conn.execute(
                f"SELECT ein, foundation_name FROM universe "
                f"WHERE ein IN ({marks})", list(eins)
            ).fetchall())
            for r in out:
                r['foundation_name'] = names.get(
                    str(r['ein']).zfill(9), ''
                )
    finally:
        conn.close()
    return {'total': total, 'total_dollars': dollars, 'page': page,
            'rows': out}


@router.get('/stats')
def grant_stats(
    q: str | None = None,
    years: list[int] = Query(default=[]),
    recipient_state: str | None = None,
    foundation_state: str | None = None,
    amount_min: int | None = None,
    amount_max: int | None = None,
    foreign_only: bool = False,
):
    where, args, join = _filters(q, years, recipient_state,
                                 foundation_state, amount_min,
                                 amount_max, foreign_only)
    conn = get_conn()
    try:
        by_state = conn.execute(
            f"SELECT g.state, COUNT(*) AS n, SUM(g.amount) AS dollars "
            f"FROM pipeline.grants g {join} WHERE {where} "
            f"AND g.state != '' GROUP BY g.state "
            f"ORDER BY dollars DESC LIMIT 55", args
        ).fetchall()
        top_recipients = conn.execute(
            f"SELECT g.grantee_name, COUNT(*) AS n, "
            f"SUM(g.amount) AS dollars FROM pipeline.grants g {join} "
            f"WHERE {where} GROUP BY g.grantee_name "
            f"ORDER BY dollars DESC LIMIT 20", args
        ).fetchall()
    finally:
        conn.close()
    return {'by_state': rows_to_dicts(by_state),
            'top_recipients': rows_to_dicts(top_recipients)}
