"""Fix 9: purity checks — flag likely classification errors before customers.

Surfaces impossible or suspicious foundation records so they can be reviewed
or excluded from prospect views.
"""

import sqlite3

from src.config import DB_PATH


def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    checks = {
        'christian > total (impossible)':
            "SELECT COUNT(*) FROM foundation_enrich "
            "WHERE christian_dollars_3yr > total_giving_3yr",
        'floor % > 100 (impossible)':
            "SELECT COUNT(*) FROM foundation_enrich "
            "WHERE christian_pct_floor > 100",
        'ceiling < floor (impossible)':
            "SELECT COUNT(*) FROM foundation_enrich "
            "WHERE christian_pct_ceiling < christian_pct_floor",
        'high floor but low coverage (<50%) — precision risk':
            "SELECT COUNT(*) FROM foundation_enrich "
            "WHERE christian_pct_floor >= 50 AND classification_coverage < 50",
        'in prospect view with coverage <50%':
            "SELECT COUNT(*) FROM foundation_enrich e "
            "WHERE christian_dollars_3yr >= 100000 "
            "AND classification_coverage < 50 AND is_testamentary_trust = 0",
    }
    print("PURITY CHECKS")
    print("=" * 60)
    for label, sql in checks.items():
        n = conn.execute(sql).fetchone()[0]
        flag = '  <-- REVIEW' if n and 'impossible' in label else ''
        print(f"  {n:>7,}  {label}{flag}")

    # concentration risk: "Funds Christian organizations" but only 3 recipients
    print("\nVerdict = strong but only 3 recipients (concentration risk):")
    n = conn.execute(
        "SELECT COUNT(*) FROM foundation_enrich WHERE "
        "verdict = 'Funds Christian organizations' "
        "AND christian_recipient_count = 3").fetchone()[0]
    print(f"  {n:,} foundations (barely clear the 3-recipient bar)")

    # corporate-named foundations tagged as strong Christian funders
    print("\nCorporate-named foundations verdict=strong (spot-check):")
    rows = conn.execute("""
        SELECT f.organization_name, e.christian_recipient_count
        FROM foundation_enrich e JOIN foundations f ON f.ein = e.ein
        WHERE e.verdict = 'Funds Christian organizations' AND (
            f.organization_name LIKE '%BANK OF AMERICA%'
            OR f.organization_name LIKE '%WALMART%'
            OR f.organization_name LIKE '%WELLS FARGO%'
            OR f.organization_name LIKE '%INSURANCE CO%')
        GROUP BY e.ein LIMIT 10
    """).fetchall()
    for r in rows:
        print(f"  {r[0][:48]:48} {r[1]} orgs")
    if not rows:
        print("  (none — good)")

    # false-negative audit: sample foundations verdict=No confirmed but with
    # a Christian-sounding name (may be under-classified)
    print("\nFalse-negative sample (No-confirmed but Christian-named):")
    rows = conn.execute("""
        SELECT f.organization_name FROM foundation_enrich e
        JOIN foundations f ON f.ein = e.ein
        WHERE e.verdict = 'No confirmed Christian giving'
        AND (f.organization_name LIKE '%CHRISTIAN%'
             OR f.organization_name LIKE '%MINISTR%'
             OR f.organization_name LIKE '%CATHOLIC%')
        AND e.total_giving_3yr > 100000 LIMIT 8
    """).fetchall()
    for r in rows:
        print(f"  {r[0][:55]}")
    if not rows:
        print("  (none — good)")
    conn.close()


if __name__ == '__main__':
    run()
