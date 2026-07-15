"""Analytics + data-quality endpoints."""

from db import data_window, get_conn, rows_to_dicts
from fastapi import APIRouter
from quality_queries import pipeline_quality

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# Known major Christian PRIVATE foundations at verified EINs.
VERIFY_EINS = [
    ("626041468", "Maclellan"),
    ("621322826", "Templeton"),
    ("237456468", "Murdock"),
    ("350868122", "Lilly"),
    ("916020515", "Stewardship"),
]


@router.get("/score-distribution")
def score_distribution():
    """Classification-coverage distribution (composite retired from UI)."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT CAST((CASE WHEN classification_coverage <= 1
                       THEN classification_coverage * 100
                       ELSE classification_coverage END) / 10 AS INT) * 10
                       AS bucket,
                   COUNT(*) AS n
            FROM universe WHERE christian_dollars_3yr > 0
            GROUP BY bucket ORDER BY bucket
        """).fetchall()
    finally:
        conn.close()
    return rows_to_dicts(rows)


@router.get("/verification")
def verification():
    conn = get_conn()
    try:
        out = []
        for ein, label in VERIFY_EINS:
            r = conn.execute(
                "SELECT foundation_name, verdict, christian_recipient_count, "
                "christian_dollars_3yr, application_status, "
                "christian_preview FROM universe WHERE ein = ?",
                (ein,),
            ).fetchone()
            if r:
                d = dict(r)
                d["label"] = label
                out.append(d)
    finally:
        conn.close()
    return out


@router.get("/leaderboards")
def leaderboards(limit: int = 10):
    conn = get_conn()
    try:
        volume = rows_to_dicts(
            conn.execute(
                "SELECT ein, foundation_name, city, state, christian_dollars_3yr, "
                "verdict, christian_recipient_count, christian_preview, "
                "application_status FROM universe "
                "WHERE christian_dollars_3yr > 0 "
                "AND (is_testamentary_trust = 0 OR is_testamentary_trust IS NULL) "
                "ORDER BY christian_dollars_3yr DESC LIMIT ?",
                (limit,),
            ).fetchall()
        )
    finally:
        conn.close()
    return {"volume": volume}


@router.get("/state-christian")
def state_christian():
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT state, COUNT(*) AS foundations,
                   SUM(christian_dollars_3yr) AS christian_dollars,
                   SUM(distributions) AS distributions
            FROM universe WHERE state != '' AND state IS NOT NULL
            GROUP BY state ORDER BY christian_dollars DESC LIMIT 20
        """).fetchall()
    finally:
        conn.close()
    return rows_to_dicts(rows)


@router.get("/size-distribution")
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
    order = ["<$10k", "$10k-100k", "$100k-1M", "$1M-10M", "$10M-100M", "$100M+"]
    data = {r["bucket"]: r["n"] for r in rows}
    return [{"bucket": b, "n": data.get(b, 0)} for b in order]


@router.get("/state-breakdown")
def state_breakdown():
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT state, COUNT(*) AS foundations,
                   SUM(distributions) AS distributions,
                   AVG(classification_coverage) AS avg_coverage,
                   SUM(CASE WHEN verdict IS NOT NULL
                       AND verdict != 'No confirmed Christian giving'
                       THEN 1 ELSE 0 END) AS faith_funders
            FROM universe WHERE state != '' AND state IS NOT NULL
            GROUP BY state ORDER BY foundations DESC
        """).fetchall()
    finally:
        conn.close()
    return rows_to_dicts(rows)


@router.get("/top-funders")
def top_funders(limit: int = 100):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ein, foundation_name, city, state, christian_dollars_3yr, "
            "verdict, christian_recipient_count, christian_preview, "
            "total_giving_3yr, application_status "
            "FROM universe WHERE christian_dollars_3yr > 0 "
            "AND (is_testamentary_trust = 0 OR is_testamentary_trust IS NULL) "
            "ORDER BY christian_dollars_3yr DESC LIMIT ?",
            (min(limit, 500),),
        ).fetchall()
    finally:
        conn.close()
    return rows_to_dicts(rows)


@router.get("/yearly-trends")
def yearly_trends():
    conn = get_conn()
    try:
        year_start, year_end = data_window(conn)
        rows = conn.execute(
            """
            SELECT tax_year, COUNT(*) AS grants, SUM(amount) AS dollars
            FROM pipeline.grants WHERE tax_year BETWEEN ? AND ?
            GROUP BY tax_year ORDER BY tax_year
        """,
            (year_start, year_end),
        ).fetchall()
    finally:
        conn.close()
    return rows_to_dicts(rows)


@router.get("/data-quality")
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
                SUM(CASE WHEN verdict IS NOT NULL
                    AND verdict != 'No confirmed Christian giving'
                    THEN 1 ELSE 0 END) AS scored,
                SUM(CASE WHEN states_given_to != ''
                    AND states_given_to IS NOT NULL THEN 1 ELSE 0 END)
                    AS with_states,
                SUM(is_testamentary_trust) AS testamentary_trusts,
                SUM(is_small_fund) AS small_funds
            FROM universe
        """).fetchone()
        year_start, year_end = data_window(conn)
        pipeline = pipeline_quality(conn, year_start, year_end)
    finally:
        conn.close()
    return {
        "universe": dict(u),
        "pipeline": {
            **pipeline,
            "tax_year_start": year_start,
            "tax_year_end": year_end,
        },
    }
