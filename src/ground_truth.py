"""Fix 6: Emily's ground-truth validation harness.

A `ground_truth` table holds foundations Emily knows cold and her estimated
Christian percentage. The report compares her estimate against our floor,
ceiling, and coverage so we can measure how close the system gets after each
classifier change. Seed rows now; Emily adds more.
"""

import sqlite3

from src.config import DB_PATH

SEED = [
    # (ein, foundation_name, emily_pct, notes)
    ('626041468', 'The Maclellan Foundation', 98,
     'Emily: gives nearly 100% to Christian nonprofits; system had shown 30%'),
    ('916020515', 'Stewardship Foundation', 95, 'Known PNW Christian funder'),
    ('237456468', 'M J Murdock Charitable Trust', 40,
     'Diversified; meaningful but not majority Christian'),
]


def ensure(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ground_truth (
            ein TEXT PRIMARY KEY, foundation_name TEXT,
            emily_estimated_christian_pct INTEGER, notes TEXT
        )""")
    for row in SEED:
        conn.execute("INSERT OR IGNORE INTO ground_truth VALUES (?,?,?,?)",
                     row)
    conn.commit()


def report(conn):
    rows = conn.execute("""
        SELECT g.foundation_name, g.emily_estimated_christian_pct est,
               e.christian_pct_floor fl, e.christian_pct_ceiling ce,
               e.classification_coverage cov
        FROM ground_truth g
        LEFT JOIN foundation_enrich e ON e.ein = g.ein
    """).fetchall()
    print(f"{'Foundation':<32}{'Emily':>6}{'Floor':>7}{'Ceil':>6}"
          f"{'Cov':>6}{'Floor Δ':>9}  In range?")
    print('-' * 78)
    for name, est, fl, ce, cov in rows:
        fl = fl or 0
        ce = ce or 0
        cov = cov or 0
        in_range = 'yes' if fl <= est <= ce else 'NO'
        print(f"{name[:31]:<32}{est:>5}%{fl:>6}%{ce:>5}%{cov:>5}%"
              f"{est - fl:>+8} {in_range:>10}")


def run():
    conn = sqlite3.connect(DB_PATH)
    ensure(conn)
    report(conn)
    conn.close()


if __name__ == '__main__':
    run()
