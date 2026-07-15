"""Diagnose the unresolved identity dollars: wall or to-do list?

Read-only (URI mode=ro; temp tables live in the separate temp database).
Every phase logs to stderr so progress is visible.
"""

from __future__ import annotations

import re
import sqlite3
import sys
import time
from pathlib import Path

RUN = "identity-20260714T014241Z"
RELIGIOUS = re.compile(
    r"\b(church(es)?|chapel|parish|congregation|cathedral|temple|synagogue|"
    r"mosque|masjid|ministr(y|ies)|diocese|archdiocese|baptist|methodist|"
    r"lutheran|presbyterian|pentecostal|episcopal|catholic|assembly of god|"
    r"gospel|bible|christian|jewish|torah|chabad|yeshiva|islamic|worship)\b")
PLACEHOLDER = re.compile(
    r"\b(various|individual|individuals|patients?|see |attached|schedule|"
    r"statement|hipp?aa?|anonymous|none|n a\b|multiple|misc|sundry|"
    r"scholarship recipients?|grant recipients?|attachment|apps? attached|"
    r"list available|available upon request|per attached|exhibit)\b|^atch\b|^see\b")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def bucket_sql(col: str) -> str:
    return f"""CASE
      WHEN {col} IS NULL OR TRIM({col})='' THEN 'blank'
      WHEN UPPER({col}) LIKE 'PC%' OR UPPER({col}) LIKE 'PUBLIC%'
        OR UPPER({col}) LIKE '509(A)%' OR UPPER({col}) LIKE '170(B)%'
        OR UPPER({col}) LIKE '501(C)(3)%' OR UPPER({col}) LIKE 'EXEMPT%'
        OR UPPER({col}) LIKE 'CHARIT%' THEN 'PC'
      WHEN UPPER({col}) LIKE 'PF%' OR UPPER({col}) LIKE 'PRIVATE%'
        OR UPPER({col}) LIKE 'POF%' THEN 'PF'
      WHEN UPPER({col}) LIKE 'NC%' OR UPPER({col}) LIKE 'NON%' THEN 'NC'
      WHEN UPPER({col}) LIKE 'GOV%' THEN 'GOV'
      WHEN UPPER({col}) IN ('I','IND') THEN 'I'
      WHEN UPPER({col}) LIKE 'CHURCH%' THEN 'CHURCH'
      ELSE 'other' END"""


def build_temp(conn: sqlite3.Connection) -> None:
    log("Phase A: building per-mention aggregate for unresolved mentions…")
    conn.execute("""
        CREATE TEMP TABLE unres_ids AS
        SELECT em.mention_id
        FROM recipient_entity_mentions em
        JOIN recipient_entities e ON e.run_id=em.run_id AND e.entity_id=em.entity_id
        WHERE em.run_id=? AND e.identity_status='unresolved'
    """, (RUN,))
    conn.execute("CREATE INDEX temp.idx_u ON unres_ids(mention_id)")
    n = conn.execute("SELECT COUNT(*) FROM unres_ids").fetchone()[0]
    log(f"  unresolved mentions: {n:,}")
    log("  joining 4.9M grant rows to funders/status (one pass)…")
    conn.execute(f"""
        CREATE TEMP TABLE unres AS
        SELECT g.mention_id,
               MAX(g.display_name) AS display_name,
               MAX(g.city) AS city, g.state AS state, MAX(g.country) AS country,
               SUM(g.signed_amount) AS paid_all,
               SUM(CASE WHEN g.tax_year IN (2023,2024) THEN g.signed_amount
                        ELSE 0 END) AS paid_2324,
               COUNT(*) AS grants,
               COUNT(DISTINCT t.ein) AS funders,
               MAX({bucket_sql('t.recipient_foundation_status')}) AS status_bucket,
               MAX(g.name_norm) AS name_norm
        FROM grant_norm g
        JOIN grant_transactions t ON t.grant_id = g.grant_id
        WHERE g.run_id=? AND g.mention_id IN (SELECT mention_id FROM unres_ids)
        GROUP BY g.mention_id
    """, (RUN,))
    total = conn.execute("SELECT COUNT(*), SUM(paid_all) FROM unres").fetchone()
    log(f"  unres table: {total[0]:,} mentions, ${total[1]/1e9:.2f}B")


def task1(conn: sqlite3.Connection) -> None:
    log("Phase B (Task 1): concentration analysis…")
    rows = conn.execute(
        "SELECT paid_all, paid_2324 FROM unres ORDER BY paid_all DESC").fetchall()
    total = sum(r[0] for r in rows)
    total24 = sum(r[1] for r in rows)
    print("\n## Task 1 — Concentration of unresolved dollars\n")
    print(f"Total unresolved: ${total/1e9:.2f}B all-time, "
          f"${total24/1e9:.2f}B in TY2023–2024, {len(rows):,} mentions\n")
    print("| Top N mentions | all-time $ | share | TY23–24 $ |")
    print("|---|---|---|---|")
    for top in (100, 500, 1_000, 5_000, 10_000, 50_000):
        s = sum(r[0] for r in rows[:top])
        s24 = sum(r[1] for r in rows[:top])
        print(f"| {top:,} | ${s/1e9:.2f}B | {100*s/total:.1f}% | ${s24/1e9:.2f}B |")
    print("\n### Top 100 unresolved mentions\n")
    print("| # | Name | City | St | Paid $ | Grants | Funders | Status |")
    print("|---|---|---|---|---|---|---|---|")
    for i, (name, city, st, paid, grants, funders, bucket) in enumerate(conn.execute(
        "SELECT display_name, city, state, paid_all, grants, funders, status_bucket "
        "FROM unres ORDER BY paid_all DESC LIMIT 100"), 1):
        print(f"| {i} | {(name or '')[:48]} | {(city or '')[:16]} | {st} "
              f"| ${paid/1e6:,.1f}M | {grants:,} | {funders:,} | {bucket} |")


def task2(conn: sqlite3.Connection) -> None:
    log("Phase C (Task 2): church / status segmentation…")
    print("\n## Task 2 — Status & religious-name segmentation\n")
    print("| recipient_foundation_status bucket | mentions | $ | share |")
    print("|---|---|---|---|")
    total = conn.execute("SELECT SUM(paid_all) FROM unres").fetchone()[0]
    for bucket, n, s in conn.execute(
        "SELECT status_bucket, COUNT(*), SUM(paid_all) FROM unres "
        "GROUP BY 1 ORDER BY 3 DESC"):
        print(f"| {bucket} | {n:,} | ${s/1e9:.2f}B | {100*s/total:.1f}% |")
    log("  scanning names for religious/placeholder patterns…")
    rel = rel_d = plc = plc_d = both = both_d = 0
    for name, paid in conn.execute("SELECT name_norm, paid_all FROM unres"):
        r = bool(RELIGIOUS.search(name or ""))
        p = bool(PLACEHOLDER.search(name or ""))
        if r:
            rel += 1
            rel_d += paid
        if p:
            plc += 1
            plc_d += paid
        if r and p:
            both += 1
            both_d += paid
    print(f"\nReligious-pattern names: {rel:,} mentions, ${rel_d/1e9:.2f}B "
          f"({100*rel_d/total:.1f}% of unresolved)")
    print(f"Placeholder-pattern names: {plc:,} mentions, ${plc_d/1e9:.2f}B "
          f"({100*plc_d/total:.1f}%)")
    print(f"(overlap: {both:,} / ${both_d/1e9:.2f}B)")
    print("\n| religious × status | mentions | $ |")
    print("|---|---|---|")
    cross: dict[tuple[str, bool], list[float]] = {}
    for name, bucket, paid in conn.execute(
        "SELECT name_norm, status_bucket, paid_all FROM unres"):
        key = (bucket, bool(RELIGIOUS.search(name or "")))
        entry = cross.setdefault(key, [0, 0.0])
        entry[0] += 1
        entry[1] += paid
    for (bucket, is_rel), (n, s) in sorted(cross.items(), key=lambda kv: -kv[1][1]):
        print(f"| {bucket} / {'religious' if is_rel else 'secular-name'} "
              f"| {n:,} | ${s/1e9:.2f}B |")


def probes(conn: sqlite3.Connection, name: str, state: str) -> list[str]:
    """Cheap BMF near-match probes for one unresolved name (read-only)."""
    variants = {name}
    variants.add(re.sub(r"^the ", "", name))
    variants.add("the " + name)
    variants.add(name + " inc")
    variants.add(re.sub(r" inc$", "", name))
    variants.add(re.sub(r"\bst\b", "saint", name))
    variants.add(re.sub(r"\bsaint\b", "st", name))
    variants.add(re.sub(r"s\b", "", name))
    found = []
    for v in variants:
        if not v or v == name and len(variants) > 1 and v is name:
            pass
        for ein, org, st in conn.execute(
            "SELECT ein, organization_name, state FROM bmf.bmf_organizations "
            "WHERE name_norm=? LIMIT 3", (v,)):
            found.append(f"{org} [{st}] EIN {ein} (variant: {v!r})")
    if not found and len(name) > 12:
        for ein, org, st in conn.execute(
            "SELECT ein, organization_name, state FROM bmf.bmf_organizations "
            "WHERE name_norm LIKE ? AND state=? LIMIT 3",
            (f"%{name[:24]}%", state)):
            found.append(f"{org} [{st}] EIN {ein} (prefix-LIKE)")
    return found[:4]


def task3(conn: sqlite3.Connection) -> None:
    log("Phase D (Task 3): stratified 50-mention sample with BMF probes…")
    rows = conn.execute(
        "SELECT display_name, name_norm, city, state, paid_all, status_bucket "
        "FROM unres ORDER BY paid_all DESC").fetchall()
    n = len(rows)
    strata = ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
              + [int(n * f) for f in (0.0001, 0.0003, 0.001, 0.002, 0.005,
                                      0.01, 0.02, 0.04, 0.07, 0.1, 0.15, 0.2,
                                      0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
              + list(range(10, 5000, 240)))
    picked = sorted({min(i, n - 1) for i in strata})[:50]
    print("\n## Task 3 — Stratified sample of 50 unresolved mentions\n")
    print("| Rank | Name | City/St | $ | Status | BMF near-matches found |")
    print("|---|---|---|---|---|---|")
    for rank in picked:
        display, name_norm, city, st, paid, bucket = rows[rank]
        hits = probes(conn, name_norm or "", st or "")
        hit_text = "; ".join(hits) if hits else "—"
        print(f"| {rank+1} | {(display or '')[:40]} | {(city or '')[:14]}/{st} "
              f"| ${paid/1e6:,.1f}M | {bucket} | {hit_text[:110]} |")


def task4(conn: sqlite3.Connection) -> None:
    log("Phase E (Task 4): recoverable-ceiling quantification…")
    print("\n## Task 4 — Recoverable ceiling (whole-population tests)\n")
    total = conn.execute("SELECT SUM(paid_all) FROM unres").fetchone()[0]
    # Every probe computes the variant on the unres side so the BMF
    # name_norm index is usable; an expression on b's side forces a
    # 1.1M x 2M nested scan (learned the hard way).
    tests = [
        ("' inc' suffix added", None,
         "b.name_norm = u.name_norm || ' inc'"),
        ("' inc' suffix removed", "u.name_norm LIKE '% inc'",
         "b.name_norm = substr(u.name_norm, 1, length(u.name_norm)-4)"),
        ("'the ' prefix removed", "u.name_norm LIKE 'the %'",
         "b.name_norm = substr(u.name_norm, 5)"),
        ("'the ' prefix added", None,
         "b.name_norm = 'the ' || u.name_norm"),
    ]
    print("| Normalization rule | mentions | $ recovered (unique-name only) |")
    print("|---|---|---|")
    for label, guard, cond in tests:
        where = f"WHERE {guard} AND" if guard else "WHERE"
        n, s = conn.execute(f"""
            SELECT COUNT(*), COALESCE(SUM(u.paid_all),0) FROM unres u
            {where} EXISTS (SELECT 1 FROM bmf.bmf_organizations b WHERE {cond})
        """).fetchone()
        print(f"| {label} | {n:,} | ${s/1e9:.2f}B |")
    n, s = conn.execute("""
        SELECT COUNT(*), COALESCE(SUM(paid_all),0) FROM unres
        WHERE country NOT IN ('US','')""").fetchone()
    print(f"| (foreign — unreachable via BMF) | {n:,} | ${s/1e9:.2f}B |")
    n, s = conn.execute("""
        SELECT COUNT(*), COALESCE(SUM(paid_all),0) FROM unres
        WHERE status_bucket='PC'""").fetchone()
    print(f"| **PC-status (990-reachable regardless of BMF)** | {n:,} "
          f"| **${s/1e9:.2f}B ({100*s/total:.1f}%)** |")
    n, s = conn.execute("""
        SELECT COUNT(*), COALESCE(SUM(paid_all),0) FROM unres
        WHERE status_bucket IN ('I','GOV')""").fetchone()
    print(f"| Individuals/Government per filer schedule | {n:,} | ${s/1e9:.2f}B |")


def main() -> None:
    db = Path("data/grants_v2.db")
    conn = sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True, timeout=60)
    conn.execute("ATTACH DATABASE ? AS bmf",
                 (f"file:{Path('data/bmf_registry.db').resolve()}?mode=ro",))
    build_temp(conn)
    task1(conn)
    task2(conn)
    task3(conn)
    task4(conn)
    log("done")


if __name__ == "__main__":
    main()
