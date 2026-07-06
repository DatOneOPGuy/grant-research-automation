"""Static HTML page: 100 foundations with full detail inlined per record.

Built for non-JS fetchers (Claude Code WebFetch) — every foundation's
scores, contacts, Christian-dollar breakdown, and top grants are rendered
directly into the HTML. Sample = top 100 Christian-dollar givers among real
prospects (testamentary trusts excluded).

Output: frontend/public/sample/index.html
"""

import html
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DB = ROOT / 'data' / 'grants.db'
OUT = ROOT / 'foundation-explorer' / 'frontend' / 'public' / 'sample' / 'index.html'
N = 100
GRANTS_PER = 8


def money(n):
    if n is None:
        return '—'
    n = float(n)
    if abs(n) >= 1e9:
        return f'${n / 1e9:.2f}B'
    if abs(n) >= 1e6:
        return f'${n / 1e6:.2f}M'
    if abs(n) >= 1e3:
        return f'${n / 1e3:.0f}k'
    return f'${n:,.0f}'


def esc(s):
    return html.escape(str(s if s is not None else '')) or '—'


def build():
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TEMP VIEW latest AS
        SELECT f.*, s.faith_alignment_score AS pct_score,
               s.christian_giving_pct, s.faith_tier, s.total_giving,
               e.faith_score_composite, e.christian_dollars_3yr,
               e.christian_dollars_2023, e.christian_dollars_2024,
               e.christian_dollars_2025, e.christian_grant_count_3yr,
               e.total_giving_3yr, e.is_testamentary_trust
        FROM foundations f
        JOIN (SELECT ein, MAX(tax_year) y FROM foundations GROUP BY ein) m
          ON f.ein = m.ein AND f.tax_year = m.y
        LEFT JOIN faith_scores s ON s.ein = f.ein
        LEFT JOIN foundation_enrich e
          ON e.ein = printf('%09d', CAST(f.ein AS INT))
    """)

    rows = conn.execute("""
        SELECT * FROM latest
        WHERE christian_dollars_3yr > 0
          AND (is_testamentary_trust = 0 OR is_testamentary_trust IS NULL)
        ORDER BY christian_dollars_3yr DESC LIMIT ?
    """, (N,)).fetchall()

    # compact summary table of all N (guaranteed fully machine-readable)
    summary_rows = ''.join(
        f"<tr><td class='r'>{i}</td><td>{esc(r['organization_name'])}</td>"
        f"<td>{esc(r['city'])}, {esc(r['state'])}</td>"
        f"<td class='r'>{r['faith_score_composite']}</td>"
        f"<td class='r'>{r['christian_giving_pct']}%</td>"
        f"<td class='r'>{money(r['christian_dollars_3yr'])}</td>"
        f"<td class='r'>{money(r['distributions'])}</td>"
        f"<td>{'Accepting' if r['has_application_info'] and not r['invite_only'] else 'Invite only' if r['invite_only'] else 'Unknown'}</td>"
        f"<td>{esc(r['contact_phone'] or r['phone'])}</td></tr>"
        for i, r in enumerate(rows, 1))
    summary = (
        "<table class='summary'><thead><tr><th class='r'>#</th>"
        "<th>Foundation</th><th>Location</th><th class='r'>Composite</th>"
        "<th class='r'>% Chr</th><th class='r'>Christian $ (3yr)</th>"
        "<th class='r'>Distributions</th><th>Application</th><th>Phone</th>"
        f"</tr></thead><tbody>{summary_rows}</tbody></table>")

    cards = []
    for i, r in enumerate(rows, 1):
        ein = r['ein']
        bare = ein.lstrip('0')
        grants = conn.execute(
            "SELECT grantee_name, city, state, country, is_foreign, amount, "
            "purpose, tax_year FROM grants WHERE ein IN (?, ?) "
            "ORDER BY amount DESC LIMIT ?", (ein, bare, GRANTS_PER)).fetchall()
        gcount, gdollars = conn.execute(
            "SELECT COUNT(*), SUM(amount) FROM grants WHERE ein IN (?, ?)",
            (ein, bare)).fetchone()

        grant_rows = ''.join(
            f"<tr><td>{esc(g['grantee_name'])}</td>"
            f"<td>{esc(g['country'] if g['is_foreign'] else g['city']+', '+str(g['state']))}</td>"
            f"<td class='r'>{money(g['amount'])}</td>"
            f"<td>{esc(g['purpose'])[:80]}</td><td class='r'>{g['tax_year']}</td></tr>"
            for g in grants)

        app = ('Accepting applications' if r['has_application_info']
               and not r['invite_only'] else
               'Invite only (call first)' if r['invite_only'] else 'Unknown')

        contact = ''
        if r['contact_person'] or r['contact_phone'] or r['deadlines']:
            contact = (
                "<div class='contact'>"
                f"<strong>Contact:</strong> {esc(r['contact_person'])} · "
                f"{esc(r['contact_phone'] or r['phone'])} · "
                f"{esc(r['contact_email'])}<br>"
                f"<strong>Address:</strong> {esc(r['contact_address'])}<br>"
                f"<strong>Application format:</strong> "
                f"{esc(r['application_format'])}<br>"
                f"<strong>Deadlines:</strong> {esc(r['deadlines'])}<br>"
                f"<strong>Restrictions:</strong> {esc(r['restrictions'])}"
                "</div>")

        cards.append(f"""
<div class="card">
  <h2>{i}. {esc(r['organization_name'])}</h2>
  <div class="sub">{esc(r['city'])}, {esc(r['state'])} · EIN {esc(ein)} ·
    Tax year {esc(r['tax_year'])} · <strong>{app}</strong> ·
    <a href="https://projects.propublica.org/nonprofits/organizations/{ein}">
    ProPublica</a></div>
  <table class="stats"><tr>
    <td><span>Composite score</span><b>{r['faith_score_composite']}</b></td>
    <td><span>Old %-only score</span><b>{r['pct_score']}</b></td>
    <td><span>% Christian giving</span><b>{r['christian_giving_pct']}%</b></td>
    <td><span>Christian $ (3yr)</span><b>{money(r['christian_dollars_3yr'])}</b></td>
    <td><span>Total giving (3yr)</span><b>{money(r['total_giving_3yr'])}</b></td>
  </tr><tr>
    <td><span>Christian $ 2023</span><b>{money(r['christian_dollars_2023'])}</b></td>
    <td><span>Christian $ 2024</span><b>{money(r['christian_dollars_2024'])}</b></td>
    <td><span>Qualifying distributions</span><b>{money(r['distributions'])}</b></td>
    <td><span>Assets</span><b>{money(r['assets'])}</b></td>
    <td><span>Website</span><b>{esc(r['website'])}</b></td>
  </tr></table>
  {contact}
  <details open><summary>Top {len(grants)} grants
    (of {gcount:,} total, {money(gdollars)})</summary>
  <table class="grants"><thead><tr><th>Recipient</th><th>Location</th>
    <th class="r">Amount</th><th>Purpose</th><th class="r">Year</th></tr></thead>
    <tbody>{grant_rows}</tbody></table></details>
</div>""")

    conn.close()

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Foundation Explorer — 100 Christian Funders (full detail)</title>
<meta name="description" content="100 US private foundations with full \
profiles: composite faith score, Christian giving by year, contacts, and \
top grants from IRS 990-PF filings.">
<style>
 body {{ font-family:-apple-system,Arial,sans-serif; color:#1a1a1a;
   background:#faf8f5; max-width:1000px; margin:0 auto; padding:2rem 1.2rem; }}
 h1 {{ font-family:Georgia,serif; color:#1a3a2e; font-size:1.8rem; }}
 p.lead {{ color:#4a4a4a; }}
 .card {{ background:#fff; border:1px solid #e5e0d5; border-radius:8px;
   padding:1.2rem 1.4rem; margin:1rem 0; }}
 .card h2 {{ font-family:Georgia,serif; color:#1a3a2e; font-size:1.15rem;
   margin:0 0 .2rem; }}
 .sub {{ color:#4a4a4a; font-size:.82rem; margin-bottom:.7rem; }}
 table.stats {{ width:100%; border-collapse:collapse; margin:.5rem 0; }}
 table.stats td {{ border:1px solid #eee; padding:.35rem .5rem; width:20%;
   vertical-align:top; }}
 table.stats span {{ display:block; font-size:.68rem; color:#9ca3af;
   text-transform:uppercase; }}
 table.stats b {{ font-size:.95rem; font-variant-numeric:tabular-nums; }}
 .contact {{ background:#faf8f5; border-radius:6px; padding:.6rem .8rem;
   font-size:.82rem; margin:.6rem 0; line-height:1.5; }}
 details {{ margin-top:.6rem; }}
 summary {{ cursor:pointer; font-size:.82rem; color:#1a3a2e; font-weight:600; }}
 table.grants {{ width:100%; border-collapse:collapse; font-size:.78rem;
   margin-top:.5rem; }}
 table.grants th,table.grants td {{ text-align:left; padding:.3rem .5rem;
   border-bottom:1px solid #eee; }}
 table.grants th {{ background:#1a3a2e; color:#fff; font-weight:500; }}
 .r {{ text-align:right; font-variant-numeric:tabular-nums; }}
 table.summary {{ width:100%; border-collapse:collapse; font-size:.75rem;
   margin:.5rem 0 2rem; }}
 table.summary th,table.summary td {{ text-align:left; padding:.28rem .45rem;
   border-bottom:1px solid #eee; }}
 table.summary th {{ background:#1a3a2e; color:#fff; font-weight:500;
   position:sticky; top:0; }}
 a {{ color:#1a3a2e; }}
 .note {{ background:#fff; border:1px solid #c9a961; border-radius:6px;
   padding:1rem; font-size:.88rem; }}
</style></head><body>
<h1>100 Christian Funders — Full Profiles</h1>
<p class="lead">The top 100 US private foundations by Christian-dollar giving
(3-year), each with its complete profile inlined: composite Faith Alignment
Score, Christian giving broken out by year, application access, contacts, and
its largest grants. Data from IRS Form 990-PF filings, tax years 2023–2025.</p>
<div class="note"><strong>For machine reading.</strong> This is a static,
fully-rendered page — every value below is in the HTML, no JavaScript required.
Scope: private foundations only (Form 990-PF); testamentary/memorial trusts
excluded. The composite score = 40% × percentage Christian giving + 60% ×
log-scaled Christian dollar volume. Note some large secular funders (Gates,
Buffett) appear because Catholic health/relief recipients are tagged Christian
by a rule-based classifier pending refinement.</div>
<h2 style="font-family:Georgia,serif;color:#1a3a2e">Summary — all 100</h2>
{summary}
<h2 style="font-family:Georgia,serif;color:#1a3a2e">Full profiles</h2>
{''.join(cards)}
<footer style="color:#9ca3af;font-size:.78rem;margin-top:2rem">
Generated from public IRS 990-PF data · Drake's Software Solutions.</footer>
</body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc)
    print(f'Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB, {len(rows)} foundations)')


if __name__ == '__main__':
    build()
