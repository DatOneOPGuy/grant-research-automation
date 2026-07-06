"""Generate the fully server-rendered static HTML report, querying the
pipeline database directly so every number is current and correct.

Covers the fix-list: corrected distributions, composite faith score with a
dollar-volume component, a Christian-giving-volume leaderboard, testamentary-
trust filtering, a verification set of known funders, and a best-prospect
universe. All content is inlined in the HTML for non-JS fetchers.
"""

import html
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DB = ROOT / 'data' / 'grants.db'
OUT = ROOT / 'foundation-explorer' / 'frontend' / 'public' / 'report' / 'index.html'

# Known major Christian PRIVATE foundations, with EINs verified against the
# database (several EINs in circulation are wrong; these are the real ones).
VERIFY = [
    ('626041468', 'The Maclellan Foundation'),
    ('621322826', 'John Templeton Foundation'),
    ('237456468', 'M J Murdock Charitable Trust'),
    ('350868122', 'Lilly Endowment'),
    ('916020515', 'Stewardship Foundation'),
    ('581493949', 'National Christian Foundation (DAF sponsor)'),
]


def money(n):
    if n is None:
        return '—'
    n = float(n)
    if abs(n) >= 1e9:
        return f'${n / 1e9:.2f}B'
    if abs(n) >= 1e6:
        return f'${n / 1e6:.1f}M'
    if abs(n) >= 1e3:
        return f'${n / 1e3:.0f}k'
    return f'${n:,.0f}'


def num(n):
    return '—' if n is None else f'{int(n):,}'


def esc(s):
    return html.escape(str(s if s is not None else ''))


def table(headers, data):
    th = ''.join(f'<th>{h}</th>' for h in headers)
    trs = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>'
                  for r in data)
    return f'<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'


def latest_foundations_view(conn):
    """Temp view: one row per EIN at its latest tax year, joined to score +
    enrichment. Distributions come from the corrected column."""
    conn.executescript("""
        CREATE TEMP VIEW latest AS
        SELECT f.ein, f.organization_name AS name, f.city, f.state,
               f.distributions, f.assets, f.revenue, f.website, f.phone,
               f.invite_only, f.has_application_info, f.tax_year,
               s.faith_alignment_score AS pct_score, s.christian_giving_pct,
               s.faith_tier,
               e.faith_score_composite, e.christian_dollars_3yr,
               e.christian_dollars_2023, e.christian_dollars_2024,
               e.christian_dollars_2025, e.christian_grant_count_3yr,
               e.total_giving_3yr, e.is_testamentary_trust,
               e.is_small_fund, e.is_actively_giving
        FROM foundations f
        JOIN (SELECT ein, MAX(tax_year) y FROM foundations GROUP BY ein) m
          ON f.ein = m.ein AND f.tax_year = m.y
        LEFT JOIN faith_scores s ON s.ein = f.ein
        LEFT JOIN foundation_enrich e ON e.ein = printf('%09d', CAST(f.ein AS INT))
    """)


def build():
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    latest_foundations_view(conn)

    total_f = conn.execute("SELECT COUNT(DISTINCT ein) FROM foundations")\
        .fetchone()[0]
    g_n, g_d = conn.execute("SELECT COUNT(*), SUM(amount) FROM grants")\
        .fetchone()
    dist_total = conn.execute(
        "SELECT SUM(distributions) FROM latest").fetchone()[0]
    scored = conn.execute(
        "SELECT COUNT(*) FROM latest WHERE pct_score IS NOT NULL")\
        .fetchone()[0]
    trusts = conn.execute(
        "SELECT SUM(is_testamentary_trust) FROM latest").fetchone()[0]
    small = conn.execute(
        "SELECT SUM(is_small_fund) FROM latest").fetchone()[0]

    kpis = table(['Metric', 'Value'], [
        ['Private foundations (entire US)', num(total_f)],
        ['Grants tracked (2023–2025 filings)', num(g_n)],
        ['Total grant dollars', money(g_d)],
        ['Total qualifying distributions (corrected)', money(dist_total)],
        ['Faith-scored foundations', num(scored)],
        ['Flagged testamentary / memorial trusts', num(trusts)],
        ['Flagged micro-funds (&lt;$10k/yr)', num(small)],
    ])

    # Leaderboard A: composite score, real prospects only
    la = conn.execute("""
        SELECT name, city, state, faith_score_composite, pct_score,
               christian_dollars_3yr, total_giving_3yr,
               CASE WHEN invite_only=1 THEN 'Invite only'
                    WHEN has_application_info=1 THEN 'Accepting'
                    ELSE 'Unknown' END AS app
        FROM latest
        WHERE faith_score_composite IS NOT NULL
          AND is_testamentary_trust = 0 AND is_small_fund = 0
          AND christian_dollars_3yr > 0
        ORDER BY faith_score_composite DESC, christian_dollars_3yr DESC
        LIMIT 100
    """).fetchall()
    lead_a = table(
        ['#', 'Foundation', 'Location', 'Composite', '% Christian',
         'Christian $ (3yr)', 'Total giving (3yr)', 'Application'],
        [[i + 1, esc(r['name']), f"{esc(r['city'])}, {esc(r['state'])}",
          r['faith_score_composite'], f"{r['pct_score']}%",
          money(r['christian_dollars_3yr']), money(r['total_giving_3yr']),
          r['app']] for i, r in enumerate(la)])

    # Leaderboard B: pure Christian-dollar volume
    lb = conn.execute("""
        SELECT name, city, state, christian_dollars_3yr, pct_score,
               faith_score_composite, christian_grant_count_3yr,
               CASE WHEN invite_only=1 THEN 'Invite only'
                    WHEN has_application_info=1 THEN 'Accepting'
                    ELSE 'Unknown' END AS app
        FROM latest
        WHERE christian_dollars_3yr > 0 AND is_testamentary_trust = 0
        ORDER BY christian_dollars_3yr DESC LIMIT 100
    """).fetchall()
    lead_b = table(
        ['#', 'Foundation', 'Location', 'Christian $ (3yr)', '% Christian',
         'Composite', 'Christian grants', 'Application'],
        [[i + 1, esc(r['name']), f"{esc(r['city'])}, {esc(r['state'])}",
          money(r['christian_dollars_3yr']), f"{r['pct_score']}%",
          r['faith_score_composite'], num(r['christian_grant_count_3yr']),
          r['app']] for i, r in enumerate(lb)])

    # Verification set
    vrows = []
    for ein, label in VERIFY:
        r = conn.execute(
            "SELECT * FROM latest WHERE ein IN (?, ?)",
            (ein, str(int(ein)))).fetchone()
        if r is None:
            vrows.append([esc(label), '<em>not in PF universe</em>',
                          '—', '—', '—', '—'])
            continue
        vrows.append([
            esc(label), esc(r['name']),
            r['pct_score'] if r['pct_score'] is not None else '—',
            r['faith_score_composite']
            if r['faith_score_composite'] is not None else '—',
            f"{r['christian_giving_pct']}%"
            if r['christian_giving_pct'] is not None else '—',
            money(r['christian_dollars_3yr'])])
    verify = table(
        ['Known funder', 'DB record', 'Old score (%-only)',
         'New composite', '% Christian', 'Christian $ (3yr)'], vrows)

    # Best-prospect universe
    prospects = conn.execute("""
        SELECT COUNT(*), SUM(christian_dollars_3yr) FROM latest
        WHERE has_application_info = 1 AND invite_only = 0
          AND faith_score_composite > 30 AND is_testamentary_trust = 0
          AND christian_dollars_3yr >= 100000
    """).fetchone()
    prospect_sample = conn.execute("""
        SELECT name, city, state, faith_score_composite,
               christian_dollars_3yr, phone, website FROM latest
        WHERE has_application_info = 1 AND invite_only = 0
          AND faith_score_composite > 30 AND is_testamentary_trust = 0
          AND christian_dollars_3yr >= 100000
        ORDER BY christian_dollars_3yr DESC LIMIT 40
    """).fetchall()
    prospect_tbl = table(
        ['Foundation', 'Location', 'Composite', 'Christian $ (3yr)',
         'Phone', 'Website'],
        [[esc(r['name']), f"{esc(r['city'])}, {esc(r['state'])}",
          r['faith_score_composite'], money(r['christian_dollars_3yr']),
          esc(r['phone'] or '—'), esc(r['website'] or '—')]
         for r in prospect_sample])

    # State breakdown with Christian dollars
    states = conn.execute("""
        SELECT state, COUNT(*) n, SUM(distributions) dist,
               SUM(christian_dollars_3yr) cd,
               AVG(faith_score_composite) avg_c
        FROM latest WHERE state != '' AND state IS NOT NULL
        GROUP BY state ORDER BY cd DESC LIMIT 20
    """).fetchall()
    state_tbl = table(
        ['State', 'Foundations', 'Total distributions',
         'Christian $ (3yr)', 'Avg composite'],
        [[r['state'], num(r['n']), money(r['dist']), money(r['cd']),
          f"{r['avg_c']:.1f}" if r['avg_c'] else '—'] for r in states])

    # Composite score distribution
    dist = conn.execute("""
        SELECT (faith_score_composite/5)*5 b, COUNT(*) n FROM latest
        WHERE faith_score_composite IS NOT NULL GROUP BY b ORDER BY b
    """).fetchall()
    dist_tbl = table(['Composite score', 'Foundations'],
                     [[f"{r['b']}–{r['b']+4}", num(r['n'])] for r in dist])

    # Size buckets (corrected distributions)
    sizes = conn.execute("""
        SELECT CASE
          WHEN distributions < 10000 THEN '1 <$10k'
          WHEN distributions < 100000 THEN '2 $10k–100k'
          WHEN distributions < 1000000 THEN '3 $100k–1M'
          WHEN distributions < 10000000 THEN '4 $1M–10M'
          WHEN distributions < 100000000 THEN '5 $10M–100M'
          ELSE '6 $100M+' END b, COUNT(*) n
        FROM latest WHERE distributions IS NOT NULL GROUP BY b ORDER BY b
    """).fetchall()
    size_tbl = table(['Total distributions', 'Foundations'],
                     [[r['b'][2:], num(r['n'])] for r in sizes])

    conn.close()

    doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Foundation Explorer — Christian Funder Report</title>
<meta name="description" content="Prerendered report of {num(total_f)} US \
private foundations scored for Christian grantmaking from IRS 990-PF filings.">
<style>
 body {{ font-family: Georgia, serif; color:#1a1a1a; background:#faf8f5;
   max-width:1150px; margin:0 auto; padding:2rem 1.5rem; line-height:1.5; }}
 h1,h2 {{ color:#1a3a2e; font-weight:600; }}
 h1 {{ font-size:2rem; margin-bottom:.25rem; }}
 h2 {{ font-size:1.25rem; margin-top:2.5rem; border-bottom:2px solid #c9a961;
   padding-bottom:.3rem; }}
 p.lead {{ color:#4a4a4a; font-size:1.05rem; }}
 table {{ border-collapse:collapse; width:100%; margin:1rem 0;
   font-family:-apple-system,Arial,sans-serif; font-size:.82rem; }}
 th,td {{ text-align:left; padding:.4rem .55rem; border-bottom:1px solid #e5e0d5; }}
 th {{ background:#1a3a2e; color:#fff; font-weight:500; }}
 td {{ font-variant-numeric:tabular-nums; }}
 tr:nth-child(even) td {{ background:#fff; }}
 .note {{ background:#fff; border:1px solid #c9a961; border-radius:6px;
   padding:1rem; font-family:-apple-system,Arial,sans-serif; font-size:.9rem; }}
 footer {{ margin-top:3rem; color:#9ca3af; font-size:.8rem;
   font-family:-apple-system,Arial,sans-serif; }}
 a {{ color:#1a3a2e; }}
</style></head><body>
<h1>Foundation Explorer — Christian Funder Report</h1>
<p class="lead">Every private foundation in the United States, scored for
Christian grantmaking from IRS Form 990-PF filings (tax years 2023–2025).
Each foundation carries both a percentage-based alignment score and a new
dollar-weighted composite score, plus its Christian giving broken out by
year, application access, and contact details.</p>

<div class="note"><strong>Scope &amp; method.</strong> This database covers
<strong>private foundations only</strong> (Form 990-PF filers) — the client
requirement. Large donor-advised-fund sponsors such as the National Christian
Foundation and The Signatry file Form 990 as public charities and are
therefore outside this universe by design. The <em>composite</em> score
combines alignment percentage (40%) with log-scaled Christian-dollar volume
(60%), so a large foundation giving tens of millions to Christian causes
outranks a tiny memorial trust giving 100% to one church. Testamentary trusts
and micro-funds are flagged and excluded from prospect views.</div>

<h2>Headline metrics</h2>
{kpis}

<h2>Verification set — known major Christian funders</h2>
<p class="lead">Spot-check: the real foundations, at their correct EINs, with
old vs. new scores. The percentage-only score buried them; the composite
score surfaces them.</p>
{verify}

<h2>Leaderboard A — Top 100 by composite score (real prospects)</h2>
<p class="lead">Excludes testamentary trusts and micro-funds.</p>
{lead_a}

<h2>Leaderboard B — Top 100 by Christian dollars given (3-year)</h2>
<p class="lead">The list a fundraiser actually uses: who moves the most money
to Christian causes, regardless of what fraction of their total that is.</p>
{lead_b}

<h2>Best-prospect universe</h2>
<p class="lead">Accepting applications, not invite-only, composite score &gt;30,
and at least $100k in Christian giving over three years:
<strong>{num(prospects[0])} foundations</strong> moving
{money(prospects[1])} to Christian causes. Top 40 shown.</p>
{prospect_tbl}

<h2>Christian giving by state (top 20)</h2>
{state_tbl}

<h2>Composite score distribution</h2>
{dist_tbl}

<h2>Foundation size — corrected total distributions</h2>
{size_tbl}

<footer>Generated from public IRS 990-PF data · Drake's Software Solutions —
Christian Foundation Database · Static report for machine/agent consumption ·
Interactive app: foundation-explorer-demo.netlify.app</footer>
</body></html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc)
    print(f'Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)')


if __name__ == '__main__':
    build()
