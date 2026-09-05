"""Explorer v5 API: composable filters over the honest v5 read model.

Read-only. Every filter maps to an indexed dimension of explorer_v5.db.
Faith filters respect the classification ledger's methods and confidence
floors; identity/classification status is first-class and never hidden.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from regions import DIVISION_NAMES, REGIONS, states_in_region

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "explorer_v5.db"
router = APIRouter(prefix="/api/v5", tags=["v5"])

# Benchmark categories that are US-facing rather than internationally
# operating, and so do not count toward the commitment tier. Mirrors
# NON_INTERNATIONAL_CATEGORIES in src/international_orgs.py -- the backend
# cannot import from src/, so a test pins the two together.
NON_INTL_CATEGORIES = ("youth",)
NON_INTL_SQL = ",".join(f"'{c}'" for c in NON_INTL_CATEGORIES)

CHRISTIAN = ("evangelical_protestant", "catholic", "orthodox_christian",
             "christian_unspecified")
TRADITIONS = {*CHRISTIAN, "jewish", "muslim", "mormon_lds",
              "christian_science", "other_religion", "secular",
              "nonchristian_unspecified", "any_christian", "unclassified"}
SORTS = {"paid": "paid_2324", "christian": "christian_dollars",
         "coverage": "coverage_pct", "assets": "assets", "name": "name",
         "median": "median_grant", "recipients": "recipient_count",
         "pct_christian": "pct_christian",
         "foreign": "foreign_dollars",
         "foreign_christian": "foreign_christian_dollars",
         "pct_foreign": "pct_foreign",
         "countries": "foreign_country_count"}
# A NULL pct_christian means "nothing could be classified", not "0% Christian".
# SQLite sorts NULLs first on DESC, which would put foundations we know
# nothing about at the top of the flagship view, so they are pushed last.
NULLS_LAST = {"pct_christian", "pct_foreign"}

# Must stay identical to FOREIGN_SQL in src/build_explorer_v5.py, or a
# foundation's per-grant international list would disagree with the
# foreign_dollars total shown above it.
# The 50 states, DC and the inhabited territories. recipient_states is built
# from whatever string the filing put in the state field, and filings are full
# of foreign regions -- ARUSHA, HERTFORDSHIRE, ONTARIO, KIGALI. 4,005 of its
# 4,061 distinct values are not US states, carrying $5.58B, and they were being
# listed and counted under a heading that says "US recipients by state".
# International giving has its own tab; this list is what makes the US one true.
US_STATES = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
    "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
    "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
    "VT", "VA", "WA", "WV", "WI", "WY", "DC", "PR", "VI", "GU", "AS",
    "MP",
    # Military postal codes -- Armed Forces Americas, Europe and Pacific.
    # US personnel at US addresses, so they belong in the US view. Without
    # them $1.63M appeared in neither the state list nor the International
    # tab, because nothing flags them as foreign either.
    "AA", "AE", "AP",
)
US_STATES_SQL = "(" + ",".join("'" + s + "'" for s in US_STATES) + ")"

FOREIGN_GRANT_SQL = (
    "(g.is_foreign=1 OR (COALESCE(g.recipient_country,'') != '' "
    "AND g.recipient_country NOT IN "
    "('', 'U.S', 'U.S.', 'UNITED STATES', 'US', 'USA')))")

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


# Whole-database aggregates that take no parameters. Each is one scan over
# millions of rows for an answer of a few dozen bytes that is identical on
# every request -- yearly-trends measured 3.5s for two rows.
#
# Caching in the process is safe here in a way it would not normally be: the
# read model is opened read-only and is never written to in place. A refresh
# builds a new file and swaps it, which restarts the service, so a cached
# value cannot outlive the data it came from. The first caller after a deploy
# pays the scan; nobody else does.
def cached_aggregate(fn):
    return lru_cache(maxsize=1)(fn)


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
    # Free-text search over the foundation's own name, plus EIN, because a
    # researcher working from a filing or a spreadsheet often has the number
    # rather than the name.
    search: str | None = None,
    recipient_search: str | None = None,
    state: str | None = None,
    gives_to_state: str | None = None,
    # Geography above and below the state. A region expands to its states, so
    # it filters the same indexed column; a county reads the rollup built by
    # src/build_geo_index.py.
    gives_to_region: str | None = None,
    gives_to_county: str | None = None,
    benchmark: str | None = None,
    min_benchmarks: int | None = None,
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
    # International giving. `country` accepts one or more filing codes
    # (FIPS, e.g. KE,UG,IN) and matches foundations that funded any of them.
    gives_internationally: bool = False,
    country: str | None = None,
    min_foreign: int | None = None,
    min_pct_foreign: float | None = None,
    min_foreign_christian: int | None = None,
    min_countries: int | None = None,
    # Must stay equal to defaultV5Filters.sort in the frontend's apiV5.ts.
    # v5FilterParams omits sort from the query string when it matches the
    # frontend default, so a disagreement here is silent: the client believes
    # it asked for one ordering and the server applies another. That is
    # exactly what happened when the frontend moved to 'christian' and this
    # still said 'paid'. tests/test_sort_defaults.py pins the pair.
    sort: str = "christian",
    order: str = Query("desc", pattern="^(asc|desc)$"),
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
    if gives_to_region:
        wanted: list[str] = []
        for name in gives_to_region.split(","):
            name = name.strip()
            if name not in REGIONS and name not in DIVISION_NAMES:
                raise HTTPException(400, f"unknown region: {name}")
            wanted += states_in_region(name)
        if wanted:
            placeholders = ",".join("?" for _ in wanted)
            where.append(
                "EXISTS (SELECT 1 FROM recipient_states rs "
                f"WHERE rs.ein=f.ein AND rs.state IN ({placeholders}))")
            params += wanted
    if gives_to_county:
        # "CA|Los Angeles County" -- the state is part of the key because
        # thirty-odd states have a Washington County.
        pairs = [c.strip() for c in gives_to_county.split(",") if "|" in c]
        if pairs:
            clauses = []
            for pair in pairs:
                st, _, county = pair.partition("|")
                clauses.append("(fc.state=? AND fc.county=?)")
                params += [st.strip().upper(), county.strip()]
            where.append(
                "EXISTS (SELECT 1 FROM foundation_counties fc "
                f"WHERE fc.ein=f.ein AND ({' OR '.join(clauses)}))")
    # International prospecting by peer. The "international" filters below
    # key off a foreign mailing address, which almost no US-based ministry
    # has -- Wycliffe is in Orlando, Samaritan's Purse in Boone -- so around
    # 90% of the funders of overseas work are invisible to them. These two
    # ask the useful question instead: who funds the major international
    # ministries. See src/international_orgs.py.
    if benchmark:
        slugs = [b.strip() for b in benchmark.split(",") if b.strip()]
        if slugs:
            marks = ",".join("?" for _ in slugs)
            where.append(
                "EXISTS (SELECT 1 FROM benchmark_hits bh "
                f"WHERE bh.ein=f.ein AND bh.slug IN ({marks}))")
            params += slugs
    if min_benchmarks:
        # Distinct ministries, not grants. One is a data point; several is a
        # deliberate international programme, which is the real signal.
        #
        # US-facing categories are excluded here. Young Life has 1,253 funders
        # against Wycliffe's 253, so counting it would inflate the top tier by
        # 39% with foundations whose international giving is nil. Those
        # ministries stay individually selectable via `benchmark`.
        where.append(
            "(SELECT COUNT(DISTINCT bh.slug) FROM benchmark_hits bh "
            " JOIN benchmark_orgs bo ON bo.slug = bh.slug "
            f" WHERE bh.ein=f.ein AND bo.category NOT IN ({NON_INTL_SQL})"
            ") >= ?")
        params.append(min_benchmarks)
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
    if search and search.strip():
        term = search.strip()
        digits = "".join(ch for ch in term if ch.isdigit())
        # Substring rather than word-boundary: this is a person typing into a
        # search box, where "endow" should find "Lilly Endowment". The
        # word-boundary discipline that governs classification rules is about
        # not asserting facts from a name, which is a different problem.
        if len(digits) == 9 and not any(ch.isalpha() for ch in term):
            where.append("f.ein = ?")
            params.append(digits)
        else:
            where.append("f.name LIKE ? ESCAPE '\\'")
            # Escape LIKE wildcards so a literal % or _ searches for itself.
            safe = (term.replace("\\", "\\\\")
                        .replace("%", "\\%").replace("_", "\\_"))
            params.append(f"%{safe}%")
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
    if gives_internationally:
        where.append("f.foreign_dollars > 0")
    if min_foreign is not None:
        where.append("f.foreign_dollars >= ?")
        params.append(min_foreign)
    if min_pct_foreign is not None:
        where.append("f.pct_foreign >= ?")
        params.append(min_pct_foreign)
    if min_foreign_christian is not None:
        where.append("f.foreign_christian_dollars >= ?")
        params.append(min_foreign_christian)
    if min_countries is not None:
        where.append("f.foreign_country_count >= ?")
        params.append(min_countries)
    if country:
        codes = [c.strip().upper() for c in country.split(",") if c.strip()]
        if codes:
            # EXISTS against the indexed rollup, not a join, so the row count
            # cannot be multiplied by a foundation funding several countries.
            where.append(f"""EXISTS (SELECT 1 FROM foundation_countries fc
                WHERE fc.ein=f.ein
                  AND fc.country_code IN ({','.join('?' for _ in codes)}))""")
            params += codes
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
                   assets, revenue, is_testamentary, is_micro,
                   foreign_dollars, foreign_grant_count, foreign_country_count,
                   foreign_top_countries, foreign_christian_dollars,
                   pct_foreign
            FROM foundations f WHERE {sql_where}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?""", [*params, limit, offset]).fetchall()
    return {"total": total, "rows": [dict(row) for row in rows]}


def _sector_breakdown(conn, ein: str) -> list[dict]:
    """Non-Christian giving by cause area, or [] if the index is absent.

    Returns the 'all' tier only. The authoritative tier exists in the table
    for parity with tradition_stats, but showing two sector tiers side by
    side asks the reader to hold a distinction that does not change what the
    money funded -- confidence is reported per sector instead.
    """
    try:
        rows = conn.execute("""
            SELECT s.sector, s.dollars, s.recipients, s.grants,
                   s.d_high, s.d_medium, s.d_low, s.d_none
            FROM sector_stats s
            WHERE s.ein = ? AND s.tier = 'all'
            ORDER BY s.dollars DESC""", (ein,)).fetchall()
    except sqlite3.OperationalError:
        return []
    # The evidence split is precomputed per (ein, sector). Deriving it here by
    # joining grants cost 525ms on a foundation with 59k of them, on every
    # panel open; this is a single indexed lookup.
    out = []
    for r in rows:
        row = dict(r)
        confidence = {k: row.pop(f"d_{k}")
                      for k in ("high", "medium", "low", "none")}
        out.append({**row,
                    "confidence": {k: v for k, v in confidence.items() if v}})
    return out


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
            f"AND state IN {US_STATES_SQL} "
            "ORDER BY dollars DESC", (ein,)).fetchall()
        # Counties for this foundation. Optional like the sector tables: a
        # read model built without src/build_geo_index.py must still serve
        # this endpoint.
        try:
            counties_rows = conn.execute(
                "SELECT state, county, dollars, grants FROM foundation_counties "
                "WHERE ein=? ORDER BY dollars DESC LIMIT 40", (ein,)).fetchall()
        except sqlite3.OperationalError:
            counties_rows = []
        countries = conn.execute(
            "SELECT country_code, country_name, dollars, grants, "
            "christian_dollars FROM foundation_countries WHERE ein=? "
            "ORDER BY dollars DESC", (ein,)).fetchall()
        # Cause areas inside the non-Christian bucket. Without this, a
        # fundraiser sees "97% non-Christian" and learns nothing about
        # whether the funder is a plausible fit; with it they can see that
        # the money went to human services, or to other grantmakers.
        #
        # Optional by design: the tables come from src/build_sector_index.py,
        # which is a separate step, and a read model built without it must
        # still serve this endpoint rather than 500.
        sectors = _sector_breakdown(conn, ein)
        # Evidence mix: how much of this foundation's classified giving rests
        # on each method. This is the rigor question a researcher should ask
        # before trusting a headline percentage, so it gets its own tab.
        methods = conn.execute("""
            SELECT COALESCE(r.method, 'unclassified') AS method,
                   SUM(CASE WHEN r.tradition IN
                        ('evangelical_protestant','catholic',
                         'orthodox_christian','christian_unspecified')
                       THEN frs.dollars ELSE 0 END) AS christian_dollars,
                   SUM(frs.dollars) AS dollars,
                   COUNT(*) AS recipients
            FROM frs JOIN recipients r ON r.entity_id=frs.entity_id
            WHERE frs.ein=? AND r.is_daf=0
            GROUP BY 1 ORDER BY 3 DESC""", (ein,)).fetchall()
        # Grant-size distribution: tells a fundraiser whether their ask fits.
        bands = conn.execute("""
            SELECT CASE
                     WHEN amount < 1000 THEN 'Under $1k'
                     WHEN amount < 5000 THEN '$1k–5k'
                     WHEN amount < 25000 THEN '$5k–25k'
                     WHEN amount < 100000 THEN '$25k–100k'
                     WHEN amount < 500000 THEN '$100k–500k'
                     WHEN amount < 1000000 THEN '$500k–1M'
                     ELSE 'Over $1M' END AS band,
                   COUNT(*) AS grants, SUM(amount) AS dollars,
                   MIN(amount) AS lo
            FROM grants WHERE funder_ein=? AND amount > 0
            GROUP BY 1 ORDER BY lo""", (ein,)).fetchall()
        yearly = conn.execute("""
            SELECT tax_year, COUNT(*) AS grants, SUM(amount) AS dollars,
                   COUNT(DISTINCT entity_id) AS recipients
            FROM grants WHERE funder_ein=? GROUP BY 1 ORDER BY 1""",
            (ein,)).fetchall()
        benchmarks = conn.execute("""
            SELECT bh.slug, bo.name, bo.category, bh.dollars, bh.grants
            FROM benchmark_hits bh JOIN benchmark_orgs bo ON bo.slug=bh.slug
            WHERE bh.ein=? ORDER BY bh.dollars DESC""", (ein,)).fetchall()
        top_foreign = conn.execute(f"""
            SELECT COALESCE(r.display_name, g.recipient_name) AS name,
                   g.country_name, g.recipient_country, g.recipient_city,
                   r.tradition, r.method,
                   SUM(g.amount) AS dollars, COUNT(*) AS grants
            FROM grants g LEFT JOIN recipients r ON r.entity_id=g.entity_id
            WHERE g.funder_ein=? AND {FOREIGN_GRANT_SQL}
            GROUP BY g.entity_id, g.country_name
            ORDER BY dollars DESC LIMIT 100""", (ein,)).fetchall()
    return {"foundation": dict(base),
            "traditions": [dict(r) for r in traditions],
            "sectors": sectors,
            "counties": [dict(r) for r in counties_rows],
            "benchmarks": [dict(r) for r in benchmarks],
            "recipients": [dict(r) for r in recipients],
            "states": [dict(r) for r in states],
            "countries": [dict(r) for r in countries],
            "methods": [dict(r) for r in methods],
            "size_bands": [dict(r) for r in bands],
            "yearly": [dict(r) for r in yearly],
            "top_foreign": [dict(r) for r in top_foreign]}


@router.get("/foundations/{ein}/recipients")
def foundation_recipients(
    ein: str,
    q: str | None = None,
    limit: int = Query(500, ge=1, le=2000),
):
    """Every organisation this foundation paid, optionally filtered by name.

    Separate from the detail endpoint, which returns only the top 500 by
    dollars. Filtering that list in the browser would search 500 of Lilly
    Endowment's 2,072 recipients and report "no match" for the other 1,572 --
    a false negative on the one question this table answers, and the kind a
    user has no way to detect.

    Matches the recipient's display name, its raw filing name, its EIN, and
    where it is -- city, county or state. A fundraiser looking at a funder
    wants to know not just who it gave to but whereabouts, and "did this
    foundation give anywhere near Dallas" is the same question as "which of
    its recipients are in Dallas County".

    Location is derived, not filed: recipients carry no address, so it comes
    from recipient_counties. 91% of recipients resolve; the rest never had a
    usable city on any grant and a location search will not return them.
    """
    where = ["frs.ein = ?"]
    params: list = [ein]
    if q and q.strip():
        term = q.strip()
        digits = "".join(c for c in term if c.isdigit())
        if len(digits) == 9 and not any(c.isalpha() for c in term):
            where.append("r.ein = ?")
            params.append(digits)
        else:
            # Escape the LIKE wildcards so a name containing % or _ is
            # searched for literally rather than matching everything.
            safe = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{safe}%"
            clauses = [
                "COALESCE(r.display_name, r.name) LIKE ? ESCAPE '\\'",
                "r.name LIKE ? ESCAPE '\\'",
                "rc.city LIKE ? ESCAPE '\\'",
                "rc.county LIKE ? ESCAPE '\\'",
            ]
            params += [like, like, like, like]
            # A bare two-letter term is a state code, not a fragment of one:
            # matching "IN" as a substring of every state would be useless.
            if len(term) == 2 and term.isalpha():
                clauses.append("rc.state = ?")
                params.append(term.upper())
            where.append("(" + " OR ".join(clauses) + ")")
    join = ("FROM frs JOIN recipients r ON r.entity_id=frs.entity_id "
            "LEFT JOIN recipient_counties rc ON rc.entity_id = frs.entity_id")
    with connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM frs WHERE ein=?", (ein,)).fetchone()[0]
        # Counted separately from the rows, which are capped by `limit`.
        # Reporting len(rows) as the match count made a search for "county"
        # say "500 of 2,072 match" when 812 did -- a precise-looking number
        # that was simply the cap, and understating in the one direction a
        # user cannot detect.
        matched = conn.execute(
            f"SELECT COUNT(*) {join} WHERE {' AND '.join(where)}",  # noqa: S608
            params).fetchone()[0]
        rows = conn.execute(f"""
            SELECT r.entity_id, COALESCE(r.display_name, r.name) AS name,
                   r.ein AS recipient_ein,
                   r.identity_status, r.tradition, r.method, r.confidence,
                   r.reason,
                   r.is_daf, (r.mission_text IS NOT NULL
                              AND r.mission_text != '') AS has_mission,
                   frs.dollars, frs.grants, frs.last_year,
                   rc.city, rc.county, rc.state
            {join}
            WHERE {' AND '.join(where)}
            ORDER BY frs.dollars DESC LIMIT ?""",
            (*params, limit)).fetchall()
    return {"total": total, "matched": matched, "returned": len(rows),
            "rows": [dict(r) for r in rows]}


@router.get("/foundations/{ein}/grants")
def foundation_grants(ein: str, limit: int = Query(200, le=1000), offset: int = 0):
    with connect() as conn:
        rows = conn.execute("""
            SELECT COALESCE(r.display_name, g.recipient_name)
                       AS recipient_name,
                   g.recipient_city, g.recipient_state,
                   g.amount, g.tax_year, g.purpose, g.entity_id,
                   r.tradition, r.identity_status,
                   g.recipient_country, g.country_name, g.is_foreign
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
@cached_aggregate
def stats():
    with connect() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS foundations,
                   SUM(paid_2324 > 0) AS active,
                   SUM(paid_2324) AS paid,
                   SUM(christian_dollars) AS christian,
                   SUM(nonchristian_dollars) AS nonchristian,
                   SUM(unclassified_dollars) AS unclassified,
                   SUM(daf_dollars) AS daf,
                   -- Dollars the filings never attributed to an organisation.
                   -- Without this the headline bar sums to $174B against $236B
                   -- paid, and the $62B difference is simply missing.
                   SUM(nonclassifiable_dollars) AS nonclassifiable
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
    # The count/sum only needs the joins when a filter reads through them.
    # Unfiltered they cost 5.9s against 0.13s for the same answer: every
    # funder_ein has a matching foundation row (verified: 0 orphans), so the
    # inner join drops nothing, and the recipients join is a LEFT one.
    needs_foundation = bool(foundation_state) or bool(q)
    needs_recipient = bool(tradition)
    joins = ""
    if needs_foundation:
        joins += " JOIN foundations f ON f.ein=g.funder_ein"
    if needs_recipient:
        joins += " LEFT JOIN recipients r ON r.entity_id=g.entity_id"

    with connect() as conn:
        agg = conn.execute(f"""
            SELECT COUNT(*) AS total, COALESCE(SUM(g.amount),0) AS total_dollars
            FROM grants g{joins}
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
    state: str | None = None,
    county: str | None = None,
    page: int = 1,
    page_size: int = Query(50, le=200),
):
    where, params = ["r.total_received > 0"], []
    # Recipient location is derived, not filed: the recipients table has no
    # address, so recipient_counties carries the place its own grants put it
    # in. 92.8% of recipients resolve; the rest had no usable city on any
    # grant and a location filter will not return them.
    if state:
        codes = [c.strip().upper() for c in state.split(",") if c.strip()]
        if codes:
            placeholders = ",".join("?" for _ in codes)
            where.append(f"rc.state IN ({placeholders})")
            params += codes
    if county:
        # "CA|Los Angeles County", matching the foundations filter's format.
        pairs = [c.split("|", 1) for c in county.split(",") if "|" in c]
        if not pairs:
            raise HTTPException(400, "county must be STATE|County Name")
        clauses = " OR ".join(
            "(rc.state = ? AND rc.county = ?)" for _ in pairs)
        where.append(f"({clauses})")
        for st, name in pairs:
            params += [st.strip().upper(), name.strip()]
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
    # LEFT JOIN so the location columns can be shown on every row, while the
    # WHERE above is what actually restricts when a filter is set.
    join = ("LEFT JOIN recipient_counties rc ON rc.entity_id = r.entity_id")
    with connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM recipients r {join} WHERE {sql_where}",  # noqa: S608
            params).fetchone()[0]
        rows = conn.execute(f"""
            SELECT r.entity_id, COALESCE(r.display_name, r.name) AS name,
                   r.ein, r.identity_status, r.tradition, r.method,
                   r.confidence, r.reason, r.is_daf, r.total_received,
                   r.funder_count, rc.state, rc.county, rc.city,
                   rc.place_count,
                   (r.mission_text IS NOT NULL AND r.mission_text != '')
                       AS has_mission
            FROM recipients r {join} WHERE {sql_where}
            ORDER BY r.total_received DESC LIMIT ? OFFSET ?""",  # noqa: S608
            [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"total": total, "rows": [dict(r) for r in rows]}


@router.get("/recipients-stats")
@cached_aggregate
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


@router.get("/countries")
def countries(christian_only: bool = False):
    """Destination countries, for the filter dropdown and the country view.

    The `(unspecified)` bucket is returned rather than hidden: a researcher
    filtering by country should be able to see how much international money we
    could not place, instead of silently comparing against a short total.
    """
    order = "christian" if christian_only else "dollars"
    with connect() as conn:
        rows = conn.execute(f"""
            SELECT country_code, country_name,
                   COUNT(DISTINCT ein) AS foundations,
                   SUM(dollars) AS dollars, SUM(grants) AS grants,
                   SUM(christian_dollars) AS christian
            FROM foundation_countries
            GROUP BY country_code, country_name
            HAVING {'SUM(christian_dollars) > 0' if christian_only else '1=1'}
            ORDER BY {order} DESC""").fetchall()
    return [dict(r) for r in rows]


@router.get("/nonprofits")
def nonprofits(
    q: str | None = None,
    # NTEE major groups, comma separated single letters: "B,X,P".
    category: str | None = None,
    # Index into sector_taxonomy.REVENUE_BANDS / ASSET_BANDS: "5,6,7".
    revenue_band: str | None = None,
    asset_band: str | None = None,
    state: str | None = None,
    # church | school | hospital | public | supporting | government | other
    org_type: str | None = None,
    # The organisation's own faith classification, where we have one.
    tradition: str | None = None,
    min_revenue: int | None = None,
    max_revenue: int | None = None,
    founded_after: int | None = None,
    founded_before: int | None = None,
    # Organisations already funded by majority-Christian foundations.
    christian_funded: bool = False,
    min_christian_funders: int | None = None,
    # Has ever received a grant from any foundation we track.
    foundation_funded: bool = False,
    has_website: bool = False,
    has_mission: bool = False,
    in_group: bool = False,
    sort: str = Query("revenue",
                      pattern="^(revenue|christian|received|assets|name|founded)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """Browse 501(c)(3) public charities -- the grant-seeking side.

    Everything else in this product looks at grantmakers. This looks at the
    organisations that approach them, which is the population our own
    prospecting and outreach works from.
    """
    # Each filter is kept separately so a facet can be recomputed with every
    # OTHER filter applied but not its own. A facet that includes its own
    # filter collapses to the one value already chosen, which makes the rail
    # useless for switching -- selecting "Religion-related" would leave
    # "Religion-related" as the only category on offer.
    clauses: dict[str, tuple[str, list]] = {}
    if q:
        clauses["q"] = ("name LIKE ?", [f"%{q}%"])
    for key, column, raw, upper in (
        ("category", "ntee_major", category, True),
        ("revenue_band", "revenue_band", revenue_band, True),
        ("asset_band", "asset_band", asset_band, True),
        ("state", "state", state, True),
        ("org_type", "org_type", org_type, False),
        ("tradition", "tradition", tradition, False),
    ):
        if not raw:
            continue
        values = [v.strip().upper() if upper else v.strip()
                  for v in raw.split(",") if v.strip()]
        if values:
            clauses[key] = (f"{column} IN ({','.join('?' for _ in values)})",
                            values)
    for key, sql, value in (
        ("min_revenue", "revenue >= ?", min_revenue),
        ("max_revenue", "revenue <= ?", max_revenue),
        ("founded_after", "ruling_year >= ?", founded_after),
        ("founded_before", "ruling_year <= ?", founded_before),
        ("min_christian_funders", "christian_funders >= ?",
         min_christian_funders),
    ):
        if value is not None:
            clauses[key] = (sql, [value])
    for key, sql, flag in (
        ("christian_funded", "christian_dollars > 0", christian_funded),
        ("foundation_funded", "total_received > 0", foundation_funded),
        ("has_website", "website IS NOT NULL", has_website),
        ("has_mission", "mission IS NOT NULL AND mission != ''", has_mission),
        ("in_group", "in_group = 1", in_group),
    ):
        if flag:
            clauses[key] = (sql, [])

    def build(exclude: str | None = None) -> tuple[str, list]:
        parts, values = ["1=1"], []
        for key, (sql, args) in clauses.items():
            if key == exclude:
                continue
            parts.append(sql)
            values += args
        return " AND ".join(parts), values

    clause, params = build()
    column = {"revenue": "revenue", "christian": "christian_dollars",
              "received": "total_received", "assets": "assets",
              "name": "name", "founded": "ruling_year"}[sort]
    direction = "ASC" if order == "asc" else "DESC"

    with connect() as conn:
        try:
            total = conn.execute(
                f"SELECT COUNT(*) FROM nonprofits WHERE {clause}",
                params).fetchone()[0]
        except sqlite3.OperationalError:
            raise HTTPException(
                503, "The nonprofit index has not been built for this read "
                     "model. Run: python3 -m src.build_nonprofit_index"
            ) from None
        rows = conn.execute(
            f"SELECT * FROM nonprofits WHERE {clause} "
            f"ORDER BY {column} {direction} LIMIT ? OFFSET ?",
            [*params, limit, offset]).fetchall()

        # Facets are grouped by the clause they need rather than queried one
        # by one. A facet only needs its own clause when its own filter is
        # active -- excluding an inactive filter is a no-op -- so with nothing
        # or one thing selected, most facets share the base clause and can be
        # counted in a single pass instead of six. Six separate scans over
        # 1.5M rows measured 4s on a common query; this is one plus one per
        # active filter.
        #
        # Paging cannot change any of them, so they are computed for the first
        # page only.
        facets: dict[str, dict] = {}
        if offset == 0:
            columns = {
                "category": ("ntee_major", True),
                "revenue_band": ("revenue_band", False),
                "asset_band": ("asset_band", False),
                "state": ("state", True),
                "org_type": ("org_type", False),
                "tradition": ("tradition", True),
            }
            if not clauses:
                # Nothing selected: every facet groups the whole table, which
                # SQLite answers straight from each column's index. Six
                # indexed scans beat one 1.5M-row pass through Python here --
                # 240ms against 1.4s.
                for key, (col, skip_null) in columns.items():
                    extra = f"AND {col} IS NOT NULL" if skip_null else ""
                    facets[key] = dict(conn.execute(
                        f"SELECT {col}, COUNT(*) FROM nonprofits "
                        f"WHERE 1=1 {extra} GROUP BY 1"))
            else:
                # Something is selected, so the indexes no longer cover the
                # predicate and each grouped scan degenerates into a table
                # lookup per row -- six of those measured 4s. One pass over
                # the matched rows, counting in Python, is far cheaper, and
                # facets sharing a clause share the pass.
                groups: dict[str, list[str]] = {}
                for key in columns:
                    # An inactive filter is a no-op to exclude, so those
                    # facets all key to the base clause and travel together.
                    groups.setdefault(key if key in clauses else "",
                                      []).append(key)

                for marker, keys in groups.items():
                    facet_clause, facet_params = build(exclude=marker or None)
                    selected = ", ".join(columns[k][0] for k in keys)
                    counts: dict[str, dict] = {k: {} for k in keys}
                    for row in conn.execute(
                            f"SELECT {selected} FROM nonprofits "
                            f"WHERE {facet_clause}", facet_params):
                        for key, value in zip(keys, row, strict=True):
                            if value is None and columns[key][1]:
                                continue
                            counts[key][value] = counts[key].get(value, 0) + 1
                    facets.update(counts)
    return {"total": total, "rows": [dict(r) for r in rows], "facets": facets}


@router.get("/analytics/non-christian")
def non_christian_overview(limit_funders: int = Query(8, ge=1, le=25)):
    """National view of the non-Christian bucket, by cause area.

    The read model reports $107B of non-Christian giving as one number. That
    is the largest figure in the product and the least informative: it says
    what the money was not, and nothing about what it was. This decomposes it
    and names the biggest funder behind each cause, so the page answers
    "who funds youth work" rather than only "how much is not Christian".
    """
    with connect() as conn:
        try:
            # Precomputed 18-row rollup. The equivalent GROUP BY scans every
            # sector_stats row -- 1.0s on the droplet -- for an answer that is
            # identical on every request.
            sectors = conn.execute(
                "SELECT * FROM sector_totals ORDER BY dollars DESC").fetchall()
        except sqlite3.OperationalError:
            raise HTTPException(
                503, "The sector index has not been built for this read "
                     "model. Run: python3 -m src.build_sector_index") from None
        if not sectors:
            raise HTTPException(503, "The sector index is empty.")


        # Top funders per sector, one indexed query each rather than a single
        # ranked scan. The window-function form is tidier to read but has to
        # sort all 403k rows: 637ms against 0ms for eighteen lookups that ride
        # idx_ss_sector(sector, tier, dollars DESC) straight to their answer.
        by_sector: dict[str, list] = {}
        for row in sectors:
            by_sector[row["sector"]] = [
                {"ein": f["ein"], "name": f["name"], "dollars": f["dollars"]}
                for f in conn.execute("""
                    SELECT ss.ein, f.name, ss.dollars
                    FROM sector_stats ss JOIN foundations f ON f.ein = ss.ein
                    WHERE ss.sector = ? AND ss.tier = 'all' AND ss.dollars > 0
                    ORDER BY ss.dollars DESC LIMIT ?""",
                    (row["sector"], limit_funders))]
    # Evidence mix nationally, summed from the same precomputed columns
    # rather than rescanning 3M grant rows -- that measured 1.1s.
    totals = {k: 0 for k in ("high", "medium", "low", "none")}
    out = []
    for r in sectors:
        row = dict(r)
        for k in totals:
            totals[k] += row.pop(f"d_{k}") or 0
        out.append({**row, "top_funders": by_sector.get(r["sector"], [])})
    return {
        "sectors": out,
        "evidence": [{"confidence": k, "dollars": v}
                     for k, v in totals.items() if v],
    }


@router.get("/counties")
def counties(state: str | None = None, q: str | None = None,
             scope: str = "funders",
             limit: int = Query(200, ge=1, le=2000)):
    """Counties that appear in the data, for the filter pickers.

    Two scopes, because the two pages ask different questions. "funders"
    counts money sent INTO a county and drives the foundations filter; and
    "recipients" counts organisations located IN one and drives the
    recipients filter. They rank differently -- a county can receive a great
    deal of money through very few organisations -- so a shared list would be
    wrong on one page or the other.

    Ordered by size, so the counties a user is likely to want are at the top
    rather than alphabetically adrift among 3,163.
    """
    if scope not in ("funders", "recipients"):
        raise HTTPException(400, "scope must be 'funders' or 'recipients'")
    p = "rc." if scope == "recipients" else ""
    where, params = ["1=1"], []
    if state:
        codes = [c.strip().upper() for c in state.split(",") if c.strip()]
        if codes:
            placeholders = ",".join("?" for _ in codes)
            where.append(f"{p}state IN ({placeholders})")
            params += codes

    # A typed query matches county names OR city names. Nobody looking for
    # funders around Brooklyn knows to type "Kings County", and nobody outside
    # Colorado knows Colorado Springs is in El Paso County. county_cities maps
    # the ~21k cities that appear on filings to their county.
    matched_city: dict[tuple[str, str], str] = {}
    if q and q.strip():
        needle = q.strip()
        like = "%" + needle.replace("%", "\\%").replace("_", "\\_") + "%"
        with connect() as conn:
            city_rows = conn.execute(
                "SELECT city, state, county FROM county_cities "
                "WHERE city LIKE ? ESCAPE '\\' "
                "ORDER BY orgs DESC LIMIT 40",
                (needle.upper().replace("%", "\\%") + "%",)).fetchall()
        clauses = [f"{p}county LIKE ? ESCAPE '\\'"]
        params.append(like)
        for row in city_rows:
            key = (row["state"], row["county"])
            # Remember the first (largest) city that pointed here, so the UI
            # can say why a county with an unrelated name is in the list.
            matched_city.setdefault(key, row["city"].title())
            clauses.append(f"({p}state = ? AND {p}county = ?)")
            params += [row["state"], row["county"]]
        where.append("(" + " OR ".join(clauses) + ")")
    sql_where = " AND ".join(where)

    if scope == "recipients":
        sql = f"""
            SELECT rc.state, rc.county, COUNT(*) AS recipients,
                   COALESCE(SUM(r.total_received), 0) AS dollars
            FROM recipient_counties rc
            JOIN recipients r ON r.entity_id = rc.entity_id
            WHERE {sql_where}
            GROUP BY rc.state, rc.county
            ORDER BY recipients DESC LIMIT ?"""  # noqa: S608
    else:
        sql = f"""
            SELECT state, county, SUM(dollars) AS dollars,
                   COUNT(DISTINCT ein) AS funders
            FROM foundation_counties
            WHERE {sql_where}
            GROUP BY state, county
            ORDER BY dollars DESC LIMIT ?"""  # noqa: S608
    with connect() as conn:
        rows = conn.execute(sql, (*params, limit)).fetchall()

    out = []
    for row in rows:
        item = dict(row)
        # Only worth saying when the county name does not already contain it.
        city = matched_city.get((row["state"], row["county"]))
        if city and city.lower() not in row["county"].lower():
            item["matched_city"] = city
        out.append(item)
    return {"rows": out}


@router.get("/benchmark-orgs")
@cached_aggregate
def benchmark_orgs():
    """The curated international-ministry list, for the filter picker.

    Grouped by category so a fundraiser can pick the peers that look like
    their own client rather than working the whole list. funders is how many
    foundations gave to each, which is what makes one a useful seed.
    """
    with connect() as conn:
        rows = conn.execute(f"""
            SELECT slug, name, category, dollars, funders, name_count,
                   CASE WHEN category IN ({NON_INTL_SQL}) THEN 0 ELSE 1 END
                       AS counts_toward_tier
            FROM benchmark_orgs ORDER BY funders DESC""").fetchall()  # noqa: S608
        # How many foundations each commitment tier would return. The filter
        # was reported as "doesn't move" on its default setting, which is
        # correct -- the default is off -- but there was no way to see what
        # any option would do before choosing it. Now the UI can say.
        counts = conn.execute(f"""
            SELECT n, COUNT(*) AS foundations FROM (
              SELECT bh.ein, COUNT(DISTINCT bh.slug) AS n
              FROM benchmark_hits bh
              JOIN benchmark_orgs bo ON bo.slug = bh.slug
              WHERE bo.category NOT IN ({NON_INTL_SQL})
              GROUP BY bh.ein)
            GROUP BY n""").fetchall()  # noqa: S608
        by_n = {r["n"]: r["foundations"] for r in counts}
    # Cumulative: "funds 3 or more" is every tier from 3 up.
    tiers = [{"min": t,
              "foundations": sum(v for n, v in by_n.items() if n >= t)}
             for t in (1, 2, 3, 5)]
    return {"rows": [dict(r) for r in rows], "tiers": tiers}


@router.get("/analytics/state-breakdown")
@cached_aggregate
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
@cached_aggregate
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
@cached_aggregate
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
