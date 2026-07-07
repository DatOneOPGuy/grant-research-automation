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

    # corporate foundations showing high Christian % (likely misclassified)
    print("\nCorporate-named foundations with floor >= 40% (spot-check):")
    rows = conn.execute("""
        SELECT f.organization_name, e.christian_pct_floor, e.classification_coverage
        FROM foundation_enrich e JOIN foundations f ON f.ein = e.ein
        WHERE e.christian_pct_floor >= 40 AND (
            f.organization_name LIKE '%BANK%' OR f.organization_name LIKE '%CORP%'
            OR f.organization_name LIKE '%WALMART%' OR f.organization_name LIKE '%INSURANCE%')
        GROUP BY e.ein LIMIT 10
    """).fetchall()
    for r in rows:
        print(f"  {r[0][:45]:45} floor={r[1]}% cov={r[2]}%")
    if not rows:
        print("  (none — good)")
    conn.close()


if __name__ == '__main__':
    run()
