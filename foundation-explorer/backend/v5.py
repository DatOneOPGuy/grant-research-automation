"""Explorer v5 API: composable filters over the honest v5 read model.

Read-only. Every filter maps to an indexed dimension of explorer_v5.db.
Faith filters respect the classification ledger's methods and confidence
floors; identity/classification status is first-class and never hidden.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "explorer_v5.db"
router = APIRouter(prefix="/api/v5", tags=["v5"])

CHRISTIAN = ("evangelical_protestant", "catholic", "orthodox_christian",
             "christian_unspecified")
TRADITIONS = {*CHRISTIAN, "jewish", "muslim", "mormon_lds",
              "christian_science", "other_religion", "secular",
              "nonchristian_unspecified", "any_christian", "unclassified"}
SORTS = {"paid": "paid_2324", "christian": "christian_dollars",
         "coverage": "coverage_pct", "assets": "assets", "name": "name",
         "median": "median_grant", "recipients": "recipient_count",
         "pct_christian": "pct_christian"}
# A NULL pct_christian means "nothing could be classified", not "0% Christian".
# SQLite sorts NULLs first on DESC, which would put foundations we know
# nothing about at the top of the flagship view, so they are pushed last.
NULLS_LAST = {"pct_christian"}

# Application-deadline seasons. Grants carry no date on a 990-PF, so these
# describe when a foundation accepts APPLICATIONS -- the thing a fundraiser
# schedules around -- not when it writes cheques.
SEASONS = {
    "spring": [3, 4, 5], "summer": [6, 7, 8],
    "fall": [9, 10, 11], "autumn": [9, 10, 11], "winter": [12, 1, 2],
    "q1": [1, 2, 3], "q2": [4, 5, 6], "q3": [7, 8, 9], "q4": [10, 11, 12],
    "first_half": [1, 2, 3, 4, 5, 6], "second_half": [7, 8, 9, 10, 11, 12],
    "year_end": [11, 12], "new_year": [1, 2],
}


def month_mask(months) -> int:
    mask = 0
    for month in months:
        if 1 <= int(month) <= 12:
            mask |= 1 << (int(month) - 1)
    return mask


def deadline_mask_from(season: str | None, months: str | None,
                       from_month: int | None, to_month: int | None) -> int:
    """Combine the three ways a user can express a window into one bitmask."""
    wanted: set[int] = set()
    for token in (season or "").split(","):
        wanted.update(SEASONS.get(token.strip().lower(), []))
    for token in (months or "").split(","):
        token = token.strip()
        if token.isdigit():
            wanted.add(int(token))
    if from_month and to_month:
        # Wraps across the year end: Nov->Feb is Nov, Dec, Jan, Feb.
        month = int(from_month)
        for _ in range(12):
            wanted.add(month)
            if month == int(to_month):
                break
            month = (month % 12) + 1
    return month_mask(wanted)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def expand_traditions(raw: str) -> list[str]:
    labels: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if token == "any_christian":
            labels.extend(CHRISTIAN)
        elif token in TRADITIONS:
            labels.append(token)
    return labels


@router.get("/foundations")
def foundations(
    tradition: str | None = None,
    tier: str = Query("any", pattern="^(any|authoritative|mission)$"),
    min_tradition_dollars: int = 0,
    min_tradition_recipients: int = 0,
    min_paid: int | None = None, max_paid: int | None = None,
    min_median: int | None = None, max_median: int | None = None,
    min_grants: int | None = None,
    active_year: int | None = Query(None, ge=2023, le=2024),
    recipient_search: str | None = None,
    state: str | None = None,
    gives_to_state: str | None = None,
    application_status: str | None = None,
    has_website: bool = False, has_email: bool = False,
    has_contact: bool = False,
    min_assets: int | None = None, max_assets: int | None = None,
    min_revenue: int | None = None,
    exclude_testamentary: bool = False, exclude_micro: bool = False,
    daf: str = Query("include", pattern="^(include|exclude|only)$"),
    coverage_band: str | None = None,
    min_coverage: float | None = None,
    min_christian: int | None = None,
    min_pct_christian: float | None = None,
    include_inactive: bool = False,
    deadline_season: str | None = None,
    deadline_months: str | None = None,
    deadline_from_month: int | None = Query(None, ge=1, le=12),
    deadline_to_month: int | None = Query(None, ge=1, le=12),
    deadline_kind: str | None = None,
    sort: str = "paid", order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, le=500), offset: int = 0,
):
    where, params = ["1=1"], []
    # A foundation that paid nothing in the window is not a prospect: no
    # grants, no faith mix, no coverage. 28,129 of them padded every result
    # set until this became the default.
    if not include_inactive:
        where.append("f.paid_2324 > 0")
    if tradition:
        labels = expand_traditions(tradition)
        if not labels:
            raise HTTPException(400, "unknown tradition")
        placeholders = ",".join("?" for _ in labels)
        where.append(f"""(
            SELECT COALESCE(SUM(dollars),0) FROM tradition_stats ts
            WHERE ts.ein=f.ein AND ts.tier=? AND ts.tradition IN ({placeholders})
        ) >= ?""")
        params += [tier, *labels, max(min_tradition_dollars, 1)]
        if min_tradition_recipients:
            where.append(f"""(
                SELECT COALESCE(SUM(recipients),0) FROM tradition_stats ts
                WHERE ts.ein=f.ein AND ts.tier=? AND ts.tradition IN ({placeholders})
            ) >= ?""")
            params += [tier, *labels, min_tradition_recipients]
    for clause, value in (
        ("f.paid_2324 >= ?", min_paid), ("f.paid_2324 <= ?", max_paid),
        ("f.median_grant >= ?", min_median), ("f.median_grant <= ?", max_median),
        ("f.grant_count_2324 >= ?", min_grants),
        ("f.assets >= ?", min_assets), ("f.assets <= ?", max_assets),
        ("f.revenue >= ?", min_revenue), ("f.coverage_pct >= ?", min_coverage),
        ("f.christian_dollars >= ?", min_christian),
    ):
        if value is not None:
            where.append(clause)
            params.append(value)
    if active_year:
        where.append(f"f.active_{active_year} = 1")
    if state:
        codes = [s.strip().upper() for s in state.split(",") if s.strip()]
        where.append(f"f.state IN ({','.join('?' for _ in codes)})")
        params += codes
    if gives_to_state:
        codes = [s.strip().upper() for s in gives_to_state.split(",") if s.strip()]
        placeholders = ",".join("?" for _ in codes)
        where.append(f"EXISTS (SELECT 1 FROM recipient_states rs "
                     f"WHERE rs.ein=f.ein AND rs.state IN ({placeholders}))")
        params += codes
    if application_status:
        statuses = [s.strip() for s in application_status.split(",")]
        where.append(
            f"f.application_status IN ({','.join('?' for _ in statuses)})")
        params += statuses
    if has_website:
        # Case-sensitive NOT IN previously let 'NA', 'n/a', 'None', 'none' and
        # 'NOT APPLICABLE' count as real websites, so foundations with no site
        # were surfaced as contactable. Mirror the frontend's websiteUrl():
        # reject placeholders case-insensitively and require a dotted host.
        where.append(
            "lower(trim(COALESCE(f.website,''))) NOT IN "
            "('','-','--','n/a','na','n.a.','none','not applicable','no',"
            "'not available','tbd','pending','null') "
            "AND instr(f.website, '.') > 0")
    if has_email:
        where.append("COALESCE(f.contact_email,'') != ''")
    if has_contact:
        where.append("(COALESCE(f.contact_person,'') != '' "
                     "OR COALESCE(f.contact_email,'') != '')")
    if exclude_testamentary:
        where.append("f.is_testamentary = 0")
    if exclude_micro:
        where.append("f.is_micro = 0")
    if daf == "exclude":
        where.append("f.daf_dollars = 0")
    elif daf == "only":
        where.append("f.daf_dollars > 0")
    if coverage_band:
        bands = [b.strip() for b in coverage_band.split(",")]
        where.append(f"f.coverage_band IN ({','.join('?' for _ in bands)})")
        params += bands
    if recipient_search:
        where.append("""EXISTS (
            SELECT 1 FROM frs JOIN recipients r ON r.entity_id=frs.entity_id
            WHERE frs.ein=f.ein AND r.name LIKE ?)""")
        params.append(f"%{recipient_search}%")
    # The rigor dial recomputes the headline number rather than only filtering
    # rows: on the authoritative tier the percentage is the authoritative-only
    # ratio, so "90% Christian" always means "of the evidence you asked for".
    pct_column = ("pct_christian_auth" if tier == "authoritative"
                  else "pct_christian")
    # Denominator stays the full classified base on both tiers -- only the
    # numerator tightens -- so the dial cannot inflate a foundation.
    order_column = SORTS.get(sort, "paid_2324")
    if order_column == "pct_christian":
        order_column = pct_column
    direction = "ASC" if order == "asc" else "DESC"
    order_sql = f"{order_column} {direction}"
    if sort in NULLS_LAST:
        order_sql = (f"({order_column} IS NULL), {order_sql}, "
                     "christian_dollars DESC")
    if min_pct_christian is not None:
        where.append(f"{pct_column} >= ?")
        params.append(min_pct_christian)
    mask = deadline_mask_from(deadline_season, deadline_months,
                              deadline_from_month, deadline_to_month)
    if mask:
        # Bitwise AND: keep foundations whose deadline months overlap the
        # requested window at all.
        where.append("(f.deadline_mask & ?) != 0")
        params.append(mask)
    if deadline_kind:
        kinds = [k.strip() for k in deadline_kind.split(",") if k.strip()]
        where.append(f"f.deadline_kind IN ({','.join('?' for _ in kinds)})")
        params += kinds
    sql_where = " AND ".join(where)
    with connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM foundations f WHERE {sql_where}", params
        ).fetchone()[0]
        rows = conn.execute(f"""
            SELECT ein, name, city, state, paid_2324, grant_count_2324,
                   recipient_count, median_grant, christian_dollars,
                   nonchristian_dollars, unclassified_dollars, daf_dollars,
                   nonclassifiable_dollars, classifiable_dollars,
                   classified_dollars,
                   {pct_column} AS pct_christian,
                   auth_christian_dollars, pct_christian_auth,
                   unattributable_reason,
                   deadline_kind, deadline_months, deadline_text,
                   coverage_pct, coverage_band, application_status, website,
                   assets, revenue, is_testamentary, is_micro
            FROM foundations f WHERE {sql_where}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?""", [*params, limit, offset]).fetchall()
    return {"total": total, "rows": [dict(row) for row in rows]}


@router.get("/foundations/{ein}")
def foundation_detail(ein: str):
    with connect() as conn:
        base = conn.execute(
            "SELECT * FROM foundations WHERE ein=?", (ein,)).fetchone()
        if base is None:
            raise HTTPException(404, "foundation not found")
        traditions = conn.execute(
            "SELECT tradition, tier, dollars, recipients FROM tradition_stats "
            "WHERE ein=? ORDER BY dollars DESC", (ein,)).fetchall()
        recipients = conn.execute("""
            SELECT r.entity_id, COALESCE(r.display_name, r.name) AS name,
                   r.ein AS recipient_ein,
                   r.identity_status, r.tradition, r.method, r.confidence,
                   r.reason,
                   r.is_daf, (r.mission_text IS NOT NULL
                              AND r.mission_text != '') AS has_mission,
                   frs.dollars, frs.grants, frs.last_year
            FROM frs JOIN recipients r ON r.entity_id=frs.entity_id
            WHERE frs.ein=? ORDER BY frs.dollars DESC LIMIT 500""",
            (ein,)).fetchall()
        states = conn.execute(
            "SELECT state, dollars FROM recipient_states WHERE ein=? "
            "ORDER BY dollars DESC", (ein,)).fetchall()
    return {"foundation": dict(base),
            "traditions": [dict(r) for r in traditions],
            "recipients": [dict(r) for r in recipients],
            "states": [dict(r) for r in states]}


@router.get("/foundations/{ein}/grants")
def foundation_grants(ein: str, limit: int = Query(200, le=1000), offset: int = 0):
    with connect() as conn:
        rows = conn.execute("""
            SELECT COALESCE(r.display_name, g.recipient_name)
                       AS recipient_name,
                   g.recipient_city, g.recipient_state,
                   g.amount, g.tax_year, g.purpose, g.entity_id,
                   r.tradition, r.identity_status
            FROM grants g LEFT JOIN recipients r ON r.entity_id=g.entity_id
            WHERE g.funder_ein=? ORDER BY g.amount DESC LIMIT ? OFFSET ?""",
            (ein, limit, offset)).fetchall()
    return {"rows": [dict(r) for r in rows]}


@router.get("/recipients/{entity_id}")
def recipient_detail(entity_id: str):
    with connect() as conn:
        base = conn.execute(
            "SELECT * FROM recipients WHERE entity_id=?", (entity_id,)).fetchone()
        if base is None:
            raise HTTPException(404, "recipient not found")
        funders = conn.execute("""
            SELECT frs.ein, f.name, frs.dollars, frs.grants, frs.last_year
            FROM frs JOIN foundations f ON f.ein=frs.ein
            WHERE frs.entity_id=? ORDER BY frs.dollars DESC LIMIT 200""",
            (entity_id,)).fetchall()
    return {"recipient": dict(base), "funders": [dict(r) for r in funders]}


@router.get("/stats")
def stats():
    with connect() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS foundations,
                   SUM(paid_2324 > 0) AS active,
                   SUM(paid_2324) AS paid,
                   SUM(christian_dollars) AS christian,
                   SUM(nonchristian_dollars) AS nonchristian,
                   SUM(unclassified_dollars) AS unclassified,
                   SUM(daf_dollars) AS daf
            FROM foundations""").fetchone()
        recipients = conn.execute(
            "SELECT COUNT(*), SUM(mission_text IS NOT NULL AND mission_text!='') "
            "FROM recipients").fetchone()
    return {**dict(row),
            "recipients": recipients[0], "with_mission": recipients[1],
            "window": "paid grants, tax years 2023-2024",
            "identity_run": "identity-20260715T164705Z"}


# --- pages beyond the foundations explorer ----------------------------------
# These serve the Grants, Recipients, Analytics and Data Quality pages, which
# were wired to the retired v1 API. Everything below reads the same v5 read
# model, so the honest-coverage semantics hold across every page.

@router.get("/grants")
def grants(
    q: str | None = None,
    recipient_state: str | None = None,
    foundation_state: str | None = None,
    amount_min: int | None = None,
    tax_year: int | None = None,
    tradition: str | None = None,
    page: int = 1,
    page_size: int = Query(50, le=200),
):
    where, params = ["1=1"], []
    if q:
        where.append("(g.recipient_name LIKE ? OR f.name LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if recipient_state:
        where.append("g.recipient_state = ?")
        params.append(recipient_state)
    if foundation_state:
        where.append("f.state = ?")
        params.append(foundation_state)
    if amount_min:
        where.append("g.amount >= ?")
        params.append(amount_min)
    if tax_year:
        where.append("g.tax_year = ?")
        params.append(tax_year)
    if tradition == "any_christian":
        where.append(f"r.tradition IN ({','.join('?' * len(CHRISTIAN))})")
        params += list(CHRISTIAN)
    elif tradition:
        where.append("r.tradition = ?")
        params.append(tradition)
    sql_where = " AND ".join(where)
    with connect() as conn:
        agg = conn.execute(f"""
            SELECT COUNT(*) AS total, COALESCE(SUM(g.amount),0) AS total_dollars
            FROM grants g JOIN foundations f ON f.ein=g.funder_ein
            LEFT JOIN recipients r ON r.entity_id=g.entity_id
            WHERE {sql_where}""", params).fetchone()  # noqa: S608
        rows = conn.execute(f"""
            SELECT COALESCE(r.display_name, g.recipient_name) AS grantee_name,
                   g.recipient_city AS city, g.recipient_state AS state,
                   g.amount, g.tax_year, g.purpose, g.entity_id,
                   f.ein, f.name AS foundation_name,
                   r.tradition, r.identity_status
            FROM grants g JOIN foundations f ON f.ein=g.funder_ein
            LEFT JOIN recipients r ON r.entity_id=g.entity_id
            WHERE {sql_where}
            ORDER BY g.amount DESC LIMIT ? OFFSET ?""",  # noqa: S608
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"total": agg["total"], "total_dollars": agg["total_dollars"],
            "rows": [dict(r) for r in rows]}


@router.get("/recipients")
def recipients(
    q: str | None = None,
    tradition: str | None = None,
    identity_status: str | None = None,
    method: str | None = None,
    min_received: int | None = None,
    page: int = 1,
    page_size: int = Query(50, le=200),
):
    where, params = ["r.total_received > 0"], []
    if q:
        where.append("r.name LIKE ?")
        params.append(f"%{q}%")
    if tradition == "any_christian":
        where.append(f"r.tradition IN ({','.join('?' * len(CHRISTIAN))})")
        params += list(CHRISTIAN)
    elif tradition == "unclassified":
        where.append("r.tradition IS NULL")
    elif tradition:
        where.append("r.tradition = ?")
        params.append(tradition)
    if identity_status:
        where.append("r.identity_status = ?")
        params.append(identity_status)
    if method:
        where.append("r.method = ?")
        params.append(method)
    if min_received:
        where.append("r.total_received >= ?")
        params.append(min_received)
    sql_where = " AND ".join(where)
    with connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM recipients r WHERE {sql_where}",  # noqa: S608
            params).fetchone()[0]
        rows = conn.execute(f"""
            SELECT r.entity_id, COALESCE(r.display_name, r.name) AS name,
                   r.ein, r.identity_status, r.tradition, r.method,
                   r.confidence, r.reason, r.is_daf, r.total_received,
                   r.funder_count,
                   (r.mission_text IS NOT NULL AND r.mission_text != '')
                       AS has_mission
            FROM recipients r WHERE {sql_where}
            ORDER BY r.total_received DESC LIMIT ? OFFSET ?""",  # noqa: S608
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"total": total, "rows": [dict(r) for r in rows]}


@router.get("/recipients-stats")
def recipients_stats():
    with connect() as conn:
        by_tradition = conn.execute("""
            SELECT COALESCE(tradition,'unclassified') AS tradition,
                   COUNT(*) AS recipients, SUM(total_received) AS dollars
            FROM recipients WHERE total_received > 0
            GROUP BY 1 ORDER BY dollars DESC""").fetchall()
        by_method = conn.execute("""
            SELECT COALESCE(method,'(none)') AS method, COUNT(*) AS recipients
            FROM recipients WHERE tradition IS NOT NULL
            GROUP BY 1 ORDER BY recipients DESC""").fetchall()
        by_identity = conn.execute("""
            SELECT identity_status, COUNT(*) AS recipients,
                   SUM(total_received) AS dollars
            FROM recipients GROUP BY 1 ORDER BY dollars DESC""").fetchall()
    return {"by_tradition": [dict(r) for r in by_tradition],
            "by_method": [dict(r) for r in by_method],
            "by_identity": [dict(r) for r in by_identity]}


@router.get("/analytics/state-breakdown")
def state_breakdown():
    with connect() as conn:
        rows = conn.execute("""
            SELECT state, COUNT(*) AS foundations, SUM(paid_2324) AS paid,
                   SUM(christian_dollars) AS christian
            FROM foundations WHERE state IS NOT NULL AND state != ''
              AND paid_2324 > 0
            GROUP BY state ORDER BY paid DESC""").fetchall()
    return [dict(r) for r in rows]


@router.get("/analytics/top-funders")
def top_funders(limit: int = Query(100, le=500), by: str = "christian"):
    column = "christian_dollars" if by == "christian" else "paid_2324"
    with connect() as conn:
        rows = conn.execute(f"""
            SELECT ein, name AS foundation_name, city, state,
                   paid_2324, christian_dollars, coverage_pct, coverage_band,
                   application_status, recipient_count
            FROM foundations WHERE {column} > 0
            ORDER BY {column} DESC LIMIT ?""", (limit,)).fetchall()  # noqa: S608
    return [dict(r) for r in rows]


@router.get("/analytics/yearly-trends")
def yearly_trends():
    with connect() as conn:
        rows = conn.execute("""
            SELECT g.tax_year, COUNT(*) AS grants, SUM(g.amount) AS paid,
                   COUNT(DISTINCT g.funder_ein) AS foundations,
                   SUM(CASE WHEN r.tradition IN
                       ('evangelical_protestant','catholic',
                        'orthodox_christian','christian_unspecified')
                       AND r.is_daf=0 THEN g.amount ELSE 0 END) AS christian
            FROM grants g LEFT JOIN recipients r ON r.entity_id=g.entity_id
            GROUP BY g.tax_year ORDER BY g.tax_year""").fetchall()
    return [dict(r) for r in rows]


@router.get("/analytics/data-quality")
def data_quality():
    with connect() as conn:
        f = conn.execute("""
            SELECT COUNT(*) AS foundations,
                   SUM(paid_2324 > 0) AS with_giving,
                   SUM(paid_2324) AS paid,
                   SUM(classifiable_dollars) AS classifiable,
                   SUM(nonclassifiable_dollars) AS nonclassifiable,
                   SUM(christian_dollars) AS christian,
                   SUM(nonchristian_dollars) AS nonchristian,
                   SUM(unclassified_dollars) AS unclassified,
                   SUM(daf_dollars) AS daf,
                   SUM(website IS NOT NULL AND website != '') AS with_website,
                   SUM(phone IS NOT NULL AND phone != '') AS with_phone,
                   SUM(contact_email IS NOT NULL AND contact_email != '')
                       AS with_email,
                   SUM(contact_person IS NOT NULL AND contact_person != '')
                       AS with_contact_person
            FROM foundations""").fetchone()
        bands = conn.execute("""
            SELECT coverage_band, COUNT(*) AS foundations,
                   SUM(paid_2324) AS paid
            FROM foundations WHERE paid_2324 > 0
            GROUP BY 1 ORDER BY foundations DESC""").fetchall()
        reasons = conn.execute("""
            SELECT COALESCE(unattributable_reason,'(none)') AS reason,
                   COUNT(*) AS foundations,
                   SUM(nonclassifiable_dollars) AS dollars
            FROM foundations WHERE nonclassifiable_dollars > 0
            GROUP BY 1 ORDER BY dollars DESC""").fetchall()
        identity = conn.execute("""
            SELECT identity_status, COUNT(*) AS recipients,
                   SUM(total_received) AS dollars
            FROM recipients GROUP BY 1 ORDER BY dollars DESC""").fetchall()
        methods = conn.execute("""
            SELECT method, COUNT(*) AS recipients FROM recipients
            WHERE tradition IS NOT NULL GROUP BY 1
            ORDER BY recipients DESC""").fetchall()
    return {"totals": dict(f), "coverage_bands": [dict(r) for r in bands],
            "unattributable_reasons": [dict(r) for r in reasons],
            "identity": [dict(r) for r in identity],
            "methods": [dict(r) for r in methods],
            "window": "paid grants, tax years 2023-2024"}
