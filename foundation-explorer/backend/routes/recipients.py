"""Recipients explorer over the active identity and classification release."""

from db import get_conn
from fastapi import APIRouter, Query
from recipient_queries import (
    list_recipients as query_recipients,
)
from recipient_queries import (
    recipient_funders as query_funders,
)
from recipient_queries import (
    recipient_stats as query_stats,
)

router = APIRouter(prefix="/api/recipients", tags=["recipients"])


@router.get("")
def list_recipients(
    q: str | None = None,
    tag: str | None = None,
    source: str | None = None,
    min_max_grant: int | None = None,
    page: int = 1,
    page_size: int = Query(default=50, le=250),
):
    conn = get_conn()
    try:
        return query_recipients(
            conn,
            q=q,
            tag=tag,
            source=source,
            min_max_grant=min_max_grant,
            page=max(1, page),
            page_size=page_size,
        )
    finally:
        conn.close()


@router.get("/stats")
def recipient_stats():
    conn = get_conn()
    try:
        return query_stats(conn)
    finally:
        conn.close()


@router.get("/{name_norm}/funders")
def recipient_funders(name_norm: str, limit: int = 50):
    conn = get_conn()
    try:
        return {"funders": query_funders(conn, name_norm, min(limit, 200))}
    finally:
        conn.close()
