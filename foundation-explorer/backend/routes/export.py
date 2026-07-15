"""Streaming CSV export of the current filtered foundation view."""

import csv
import io

from db import get_conn
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from models import FoundationFilters, foundation_filters_dep
from queries import foundation_filters, order_clause

router = APIRouter(prefix='/api/export', tags=['export'])

EXPORT_COLS = [
    'ein', 'foundation_name', 'city', 'state', 'ntee_code', 'data_found',
    'latest_tax_year', 'revenue', 'assets', 'distributions',
    'application_status', 'website', 'phone', 'contact_person',
    'contact_address', 'contact_email', 'application_format', 'deadlines',
    'restrictions', 'states_given_to', 'faith_alignment_score',
    'faith_tier', 'faith_stars', 'faith_categories',
    'christian_giving_pct', 'propublica_url',
]


@router.get('/foundations.csv')
def export_foundations(
    p: FoundationFilters = Depends(foundation_filters_dep),
):
    where, args = foundation_filters(p)
    order = order_clause(p.sort, p.direction)
    cols = ', '.join(f'"{c}"' for c in EXPORT_COLS)

    def generate():
        conn = get_conn()
        try:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(EXPORT_COLS)
            yield buf.getvalue()
            cursor = conn.execute(
                f"SELECT {cols} FROM universe WHERE {where} {order}",
                args,
            )
            while True:
                rows = cursor.fetchmany(2000)
                if not rows:
                    break
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerows(rows)
                yield buf.getvalue()
        finally:
            conn.close()

    return StreamingResponse(
        generate(), media_type='text/csv',
        headers={'Content-Disposition':
                 'attachment; filename=foundations_filtered.csv'},
    )
