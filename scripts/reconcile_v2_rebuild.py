"""Reconcile the reparsed grants DB against the prior build, side by side.

Read-only against both databases. Every metric that should be unchanged by
the address fix must match exactly; any drift is a red flag to investigate
before identity resolution builds on the new data.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

OLD = Path(sys.argv[1] if len(sys.argv) > 1 else "data/grants_v2.db")
NEW = Path(sys.argv[2] if len(sys.argv) > 2 else "data/grants_v2_new.db")

METRICS: list[tuple[str, str]] = [
    ("XMLs parsed (all filings rows)", "SELECT COUNT(*) FROM filings"),
    ("990-PF accepted (parse_status=parsed)",
     "SELECT COUNT(*) FROM filings WHERE parse_status='parsed'"),
    ("Non-990-PF excluded",
     "SELECT COUNT(*) FROM filings WHERE parse_status='excluded_return_type'"),
    ("Other parse statuses",
     "SELECT COUNT(*) FROM filings "
     "WHERE parse_status NOT IN ('parsed','excluded_return_type')"),
    ("Canonical foundation-years", "SELECT COUNT(*) FROM canonical_filings"),
    ("Amended filings (is_amended=1)",
     "SELECT COUNT(*) FROM filings WHERE is_amended=1"),
    ("Duplicate EIN/year groups",
     "SELECT COUNT(*) FROM (SELECT ein, tax_year FROM filings "
     "WHERE parse_status='parsed' GROUP BY ein, tax_year HAVING COUNT(*)>1)"),
    ("Paid positive rows",
     "SELECT COUNT(*) FROM canonical_grants "
     "WHERE schedule_type='paid' AND amount_status='positive'"),
    ("Paid positive dollars",
     "SELECT SUM(signed_amount) FROM canonical_grants "
     "WHERE schedule_type='paid' AND amount_status='positive'"),
    ("Future positive rows",
     "SELECT COUNT(*) FROM canonical_grants "
     "WHERE schedule_type='future_approved' AND amount_status='positive'"),
    ("Future positive dollars",
     "SELECT SUM(signed_amount) FROM canonical_grants "
     "WHERE schedule_type='future_approved' AND amount_status='positive'"),
    ("Paid zero rows",
     "SELECT COUNT(*) FROM canonical_grants "
     "WHERE schedule_type='paid' AND amount_status='zero'"),
    ("Paid negative rows",
     "SELECT COUNT(*) FROM canonical_grants "
     "WHERE schedule_type='paid' AND amount_status='negative'"),
    ("Paid missing rows",
     "SELECT COUNT(*) FROM canonical_grants "
     "WHERE schedule_type='paid' AND amount_status='missing'"),
    ("Paid invalid rows",
     "SELECT COUNT(*) FROM canonical_grants "
     "WHERE schedule_type='paid' AND amount_status='invalid'"),
    ("Non-990-PF canonical filings",
     "SELECT COUNT(*) FROM canonical_filings c JOIN filings f USING(object_id) "
     "WHERE f.return_type != '990PF'"),
    ("Canonical-policy mismatches",
     """
     WITH ranked AS (
       SELECT ein, tax_year, object_id,
              ROW_NUMBER() OVER (
                PARTITION BY ein, tax_year
                ORDER BY COALESCE(return_timestamp_utc,'') DESC,
                         is_amended DESC, object_id DESC
              ) AS rn
       FROM filings WHERE parse_status='parsed'
     )
     SELECT COUNT(*) FROM canonical_filings c
     JOIN ranked r ON r.ein=c.ein AND r.tax_year=c.tax_year AND r.rn=1
     WHERE r.object_id != c.object_id
     """),
]

NEW_ONLY: list[tuple[str, str]] = [
    ("Paid rows w/ city",
     "SELECT printf('%d (%.1f%%)', SUM(recipient_city!=''), "
     "100.0*SUM(recipient_city!='')/COUNT(*)) FROM canonical_grants "
     "WHERE schedule_type='paid' AND amount_status='positive'"),
    ("Paid rows w/ state",
     "SELECT printf('%d (%.1f%%)', SUM(recipient_state!=''), "
     "100.0*SUM(recipient_state!='')/COUNT(*)) FROM canonical_grants "
     "WHERE schedule_type='paid' AND amount_status='positive'"),
    ("Paid rows foreign",
     "SELECT printf('%d (%.2f%%)', SUM(is_foreign), "
     "100.0*SUM(is_foreign)/COUNT(*)) FROM canonical_grants "
     "WHERE schedule_type='paid' AND amount_status='positive'"),
]


def fetch(conn: sqlite3.Connection, sql: str):
    try:
        return conn.execute(sql).fetchone()[0]
    except sqlite3.Error as error:
        return f"ERROR: {error}"


def fmt(value) -> str:
    if isinstance(value, int) and abs(value) >= 10_000_000:
        return f"{value:,} (${value/1e9:.2f}B)"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def main() -> None:
    old = sqlite3.connect(f"file:{OLD.resolve()}?mode=ro", uri=True, timeout=60)
    new = sqlite3.connect(f"file:{NEW.resolve()}?mode=ro", uri=True, timeout=60)
    mismatches = 0
    print(f"| Metric | old ({OLD.name}) | new ({NEW.name}) | match |")
    print("|---|---|---|---|")
    for label, sql in METRICS:
        old_value, new_value = fetch(old, sql), fetch(new, sql)
        ok = old_value == new_value
        mismatches += (not ok)
        print(f"| {label} | {fmt(old_value)} | {fmt(new_value)} | "
              f"{'✅' if ok else '❌ MISMATCH'} |")
    print("\n**New-field coverage (new DB only):**\n")
    print("| Field | value |")
    print("|---|---|")
    for label, sql in NEW_ONLY:
        print(f"| {label} | {fetch(new, sql)} |")
    print("\n| recipient_foundation_status | rows |")
    print("|---|---|")
    for status, count in new.execute(
        "SELECT COALESCE(NULLIF(recipient_foundation_status,''),'(blank)'), COUNT(*) "
        "FROM canonical_grants WHERE schedule_type='paid' AND amount_status='positive' "
        "GROUP BY 1 ORDER BY 2 DESC LIMIT 12"
    ):
        print(f"| {status} | {count:,} |")
    print(f"\nRESULT: {'RECONCILED' if mismatches == 0 else f'{mismatches} MISMATCH(ES)'}")
    sys.exit(0 if mismatches == 0 else 1)


if __name__ == "__main__":
    main()
