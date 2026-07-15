"""Step 6 completion report: fetch/parse outcomes, per-list yield, coverage.

Read-only. Also re-verifies that grant paid totals are unchanged (this build
is additive documentary evidence, not a grants re-parse).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

conn = sqlite3.connect(
    f"file:{Path('data/grants_v2.db').resolve()}?mode=ro", uri=True, timeout=60)
run_id = conn.execute(
    "SELECT run_id FROM identity_runs ORDER BY created_at_utc DESC LIMIT 1"
).fetchone()[0]

print("## Fetch / parse outcomes\n")
total, fetched = conn.execute(
    "SELECT COUNT(*), SUM(fetched) FROM r990_fetch_list WHERE identity_run_id=?",
    (run_id,)).fetchone()
print(f"- fetch list: {total:,} filings; fetched {fetched:,} "
      f"({100*fetched/total:.1f}%)")
for status, count in conn.execute(
    "SELECT parse_status, COUNT(*) FROM r990_documents GROUP BY 1"):
    print(f"- parse {status}: {count:,}")
with_mission = conn.execute(
    "SELECT COUNT(*), SUM(mission_text!=''), "
    "SUM(program_texts_json!='[]') FROM r990_documents "
    "WHERE parse_status='parsed'").fetchone()
print(f"- parsed docs: {with_mission[0]:,}; with mission text "
      f"{with_mission[1]:,}; with program text {with_mission[2]:,}")

print("\n## Per-list yield (targets whose EIN has >=1 parsed 990/990-EZ)\n")
print("| List | targets | with filing | $ targeted (TY23-24) | $ covered |")
print("|---|---|---|---|---|")
for lst in ("A", "B", "C"):
    row = conn.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN d.ein IS NOT NULL THEN 1 ELSE 0 END),
               SUM(t.paid_2324),
               SUM(CASE WHEN d.ein IS NOT NULL THEN t.paid_2324 ELSE 0 END)
        FROM r990_targets t
        LEFT JOIN (SELECT DISTINCT ein FROM r990_documents
                   WHERE parse_status='parsed') d ON d.ein = t.matched_ein
        WHERE t.identity_run_id=? AND t.target_list=?
    """, (run_id, lst)).fetchone()
    targets, covered, dollars, dollars_covered = row
    print(f"| {lst} | {targets:,} | {covered:,} ({100*covered/max(targets,1):.1f}%) "
          f"| ${(dollars or 0)/1e9:.2f}B | ${(dollars_covered or 0)/1e9:.2f}B |")

print("\n## List B match funnel (honest misses)\n")
for status, count, dollars in conn.execute("""
    SELECT match_status, COUNT(*), SUM(paid_2324) FROM r990_targets
    WHERE identity_run_id=? AND target_list='B' GROUP BY 1 ORDER BY 2 DESC
""", (run_id,)):
    print(f"- {status}: {count:,} (${(dollars or 0)/1e9:.2f}B)")

print("\n## Documentary text for name-neutral entities\n")
neutral = conn.execute("""
    SELECT COUNT(DISTINCT e.entity_id)
    FROM recipient_entities e
    JOIN r990_documents d ON d.ein = e.bmf_ein AND d.parse_status='parsed'
        AND d.mission_text != ''
    WHERE e.run_id=? AND e.identity_status='matched_bmf'
      AND e.entity_id NOT IN (
        SELECT entity_id FROM classification_evidence
        WHERE identity_run_id=? AND evidence_method='rule')
""", (run_id, run_id)).fetchone()[0]
print(f"- name-neutral matched entities that now have their own mission text: "
      f"{neutral:,}")

print("\n## Reconciliation (must be unchanged)\n")
paid = conn.execute(
    "SELECT COUNT(*), SUM(signed_amount) FROM canonical_grants "
    "WHERE schedule_type='paid' AND amount_status='positive'").fetchone()
print(f"- paid positive rows: {paid[0]:,} (expect 4,892,327)")
print(f"- paid positive dollars: ${paid[1]:,} (expect $365,538,055,855)")
print(f"- RECONCILED: {paid == (4892327, 365538055855)}")
