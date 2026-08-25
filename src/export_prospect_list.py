"""Outreach list: nonprofits (not foundations) above a revenue floor.

    python3 -m src.export_prospect_list
    python3 -m src.export_prospect_list --min-revenue 800000 --out list.csv

Source is the IRS Business Master File plus our own grant data. Deliberately
not ProPublica: their Data Terms of Use prohibit commercial use and prohibit
redistributing the data on a stand-alone basis, and a spreadsheet handed to a
colleague to sell from is both. The BMF is a public-domain federal dataset
with no such restriction, and it carries the revenue figure directly.

Who is included
---------------
Active 501(c)(3) public charities above the revenue floor. Private
foundations are excluded by foundation_code (02, 03, 04) -- they are
grantmakers, not the people who need help finding grantmakers.

Why it is ranked rather than dumped
-----------------------------------
123,222 organisations clear the $800k floor. A list that size is not a
prospect list, it is a spam list, and sending to all of it would damage the
sending domain long before it produced a customer. So every row carries a
tier, and the tiers are ordered by how directly this product serves them:

  A  faith-classified AND already funded by majority-Christian foundations
  B  already funded by majority-Christian foundations
  C  faith-classified, no Christian foundation money we can see
  D  everything else

Tier A is the warmest because those organisations are demonstrably inside the
Christian funding ecosystem this product maps -- the pitch is about a tool
they would already have a use for, not a cold introduction to the category.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

from src.sector_taxonomy import label, sector_from_ntee

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "explorer_v5.db"
DEFAULT_BMF = ROOT / "data" / "bmf_registry.db"
DEFAULT_OUT = ROOT / "nonprofit_prospects.csv"

# Private foundation determinations. These are grantmakers.
FOUNDATION_CODES = ("02", "03", "04")

FAITH_LABELS = {
    "evangelical_protestant": "Evangelical / Protestant",
    "catholic": "Catholic",
    "orthodox_christian": "Orthodox",
    "christian_unspecified": "Christian (unspecified)",
    "christian_science": "Christian Science",
    "jewish": "Jewish",
    "muslim": "Muslim",
    "mormon_lds": "Latter-day Saints",
    "other_religion": "Other religion",
    "secular": "Secular",
}
CHRISTIAN = ("evangelical_protestant", "catholic", "orthodox_christian",
             "christian_unspecified")

COLUMNS = [
    "tier", "organization", "ein", "city", "state", "revenue",
    "sector", "faith", "christian_funding_received", "christian_funders",
    "website", "mission", "propublica",
]

QUERY = f"""
SELECT b.ein, b.organization_name, b.city, b.state, b.income_amount,
       b.ntee_code,
       rc.tradition, rc.website, rc.mission_text,
       COALESCE(cf.dollars, 0) AS christian_dollars,
       COALESCE(cf.funders, 0) AS christian_funders
FROM bmf.bmf_organizations b
LEFT JOIN recipients rc ON rc.ein = b.ein
LEFT JOIN (
    SELECT g.entity_id,
           SUM(g.amount) AS dollars,
           COUNT(DISTINCT g.funder_ein) AS funders
    FROM grants g
    JOIN foundations f ON f.ein = g.funder_ein
    WHERE f.pct_christian >= 50
    GROUP BY g.entity_id
) cf ON cf.entity_id = rc.entity_id
WHERE b.income_amount > ?
  AND b.status_code = '01'
  AND b.subsection_code = '03'
  AND b.foundation_code NOT IN {FOUNDATION_CODES}
"""


def clean_website(raw: str | None) -> str:
    value = (raw or "").strip()
    if value.lower() in ("", "n/a", "na", "none", "null"):
        return ""
    if "@" in value and "/" not in value:
        return ""          # an email in the website field is not a website
    if not value.lower().startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


def tier_of(tradition: str | None, christian_dollars: float) -> str:
    faith = tradition in CHRISTIAN
    funded = christian_dollars > 0
    if faith and funded:
        return "A"
    if funded:
        return "B"
    if faith:
        return "C"
    return "D"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-revenue", type=int, default=800_000)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--bmf", default=str(DEFAULT_BMF))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--tiers", default="ABCD",
                        help="which tiers to include, e.g. AB")
    args = parser.parse_args()

    for path in (Path(args.db), Path(args.bmf)):
        if not path.exists():
            print(f"ERROR: missing {path}", file=sys.stderr)
            return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.execute(f"ATTACH 'file:{args.bmf}?mode=ro' AS bmf")
    conn.row_factory = sqlite3.Row

    wanted = set(args.tiers.upper())
    rows = []
    for r in conn.execute(QUERY, (args.min_revenue,)):
        tier = tier_of(r["tradition"], r["christian_dollars"])
        if tier not in wanted:
            continue
        sector = sector_from_ntee(r["ntee_code"])
        mission = (r["mission_text"] or "").strip().replace("\n", " ")
        rows.append({
            "tier": tier,
            "organization": (r["organization_name"] or "").strip(),
            "ein": r["ein"],
            "city": (r["city"] or "").title(),
            "state": r["state"] or "",
            "revenue": int(r["income_amount"] or 0),
            "sector": label(sector) if sector else "",
            "faith": FAITH_LABELS.get(r["tradition"] or "", ""),
            "christian_funding_received": int(r["christian_dollars"] or 0),
            "christian_funders": int(r["christian_funders"] or 0),
            "website": clean_website(r["website"]),
            "mission": mission[:300],
            "propublica":
                f"https://projects.propublica.org/nonprofits/organizations/{r['ein']}",
        })
    conn.close()

    # Tier first, then the size of the Christian relationship, then revenue.
    # Within a tier, an organisation already taking real money from Christian
    # funders is a better conversation than a larger one that is not.
    rows.sort(key=lambda x: (x["tier"], -x["christian_funding_received"],
                             -x["revenue"]))

    out = Path(args.out)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["tier"]] = counts.get(row["tier"], 0) + 1
    print(f"wrote {len(rows):,} rows to {out}")
    for tier in sorted(counts):
        with_site = sum(1 for r in rows if r["tier"] == tier and r["website"])
        print(f"  tier {tier}: {counts[tier]:>7,}  ({with_site:,} with a website)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
