"""Build the human-review alias queue: top unresolved mentions by TY23-24 $.

For each mention, propose BMF candidates via deterministic probes a human can
adjudicate: IRS-truncation equivalence (TRUST->TR, FOUNDATION->FDN, ...),
distinctive-token containment in-state then national, and DAF-sponsor name
patterns (flagged as their own category). Proposals are suggestions with
reasoning — nothing is written anywhere until rows are explicitly approved
into identity_aliases. Read-only.
"""

from __future__ import annotations

import csv
import re
import sqlite3
import sys
import time
from pathlib import Path

RUN = None  # latest
QUEUE_SIZE = 500
TRUNCATIONS = [
    ("trust", "tr"), ("foundation", "fdn"), ("foundation", "found"),
    ("association", "assn"), ("charitable", "charitbl"),
    ("incorporated", "inc"), ("corporation", "corp"), ("company", "co"),
    ("university", "univ"), ("institute", "inst"), ("center", "ctr"),
    ("memorial", "mem"), ("national", "natl"), ("international", "intl"),
]
DAF_PATTERN = re.compile(
    r"\b(donor advised|charitable gift fund|charitable fund|giving fund|"
    r"philanthropic tr(ust)?|community foundation|charitable trust co|"
    r"national philanthropic|donors? trust|fidelity charitable|"
    r"schwab charitable|vanguard charitable|american online giving|"
    r"national christian foundation|charityvest|daffy|american endowment)\b")
STOPWORDS = {"the", "of", "and", "for", "a", "in", "inc", "foundation",
             "fund", "trust", "charitable", "association", "society",
             "america", "american", "national", "international", "center",
             "institute", "university", "college", "corporation", "company"}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def truncation_variants(name: str) -> set[str]:
    tokens = name.split()
    variants = set()
    for full, short in TRUNCATIONS:
        if full in tokens:
            variants.add(" ".join(short if t == full else t for t in tokens))
        if short in tokens:
            variants.add(" ".join(full if t == short else t for t in tokens))
    return variants


def distinctive_tokens(name: str) -> list[str]:
    return [t for t in name.split() if t not in STOPWORDS and len(t) > 3][:3]


def propose(conn: sqlite3.Connection, name: str, state: str) -> list[tuple]:
    """Return up to 3 (ein, bmf_name, bmf_city, bmf_state, method) proposals."""
    out: list[tuple] = []
    seen: set[str] = set()

    def add(rows, method):
        for ein, org, city, st in rows:
            if ein not in seen:
                seen.add(ein)
                out.append((ein, org, city, st, method))

    for variant in truncation_variants(name):
        add(conn.execute(
            "SELECT ein, organization_name, city, state FROM bmf.bmf_organizations "
            "WHERE name_norm=? LIMIT 2", (variant,)), "irs_truncation")
    tokens = distinctive_tokens(name)
    if tokens and len(out) < 3:
        like = "%" + "%".join(tokens) + "%"
        if state:
            add(conn.execute(
                "SELECT ein, organization_name, city, state "
                "FROM bmf.bmf_organizations "
                "WHERE state=? AND name_norm LIKE ? LIMIT 3",
                (state, like)), "token_containment_state")
        if not out:
            add(conn.execute(
                "SELECT ein, organization_name, city, state "
                "FROM bmf.bmf_organizations WHERE name_norm LIKE ? LIMIT 3",
                (like,)), "token_containment_national")
    return out[:3]


def main() -> None:
    conn = sqlite3.connect(
        f"file:{Path('data/grants_v2.db').resolve()}?mode=ro", uri=True, timeout=60)
    conn.execute("ATTACH DATABASE ? AS bmf",
                 (f"file:{Path('data/bmf_registry.db').resolve()}?mode=ro",))
    run_id = conn.execute(
        "SELECT run_id FROM identity_runs ORDER BY created_at_utc DESC LIMIT 1"
    ).fetchone()[0]
    log(f"building TY23-24 dollars for unresolved mentions (run {run_id})…")
    conn.execute("""
        CREATE TEMP TABLE unres_2324 AS
        SELECT g.mention_id, MAX(g.display_name) AS display_name,
               MAX(g.name_norm) AS name_norm, MAX(g.city) AS city,
               g.state AS state,
               SUM(CASE WHEN g.tax_year IN (2023,2024)
                        THEN g.signed_amount ELSE 0 END) AS paid_2324,
               SUM(g.signed_amount) AS paid_all,
               COUNT(DISTINCT t.ein) AS funders
        FROM grant_norm g
        JOIN grant_transactions t ON t.grant_id=g.grant_id
        JOIN recipient_entity_mentions em
          ON em.run_id=g.run_id AND em.mention_id=g.mention_id
        JOIN recipient_entities e
          ON e.run_id=em.run_id AND e.entity_id=em.entity_id
        WHERE g.run_id=? AND e.identity_status='unresolved'
        GROUP BY g.mention_id
    """, (run_id,))
    rows = conn.execute(
        "SELECT display_name, name_norm, city, state, paid_2324, paid_all, "
        "funders FROM unres_2324 ORDER BY paid_2324 DESC, paid_all DESC LIMIT ?",
        (QUEUE_SIZE,)).fetchall()
    log(f"queue built: {len(rows)} rows; probing BMF for proposals…")
    writer = csv.writer(sys.stdout)
    writer.writerow(["rank", "filed_name", "name_norm", "city", "state",
                     "paid_2324", "paid_all", "funders", "category",
                     "proposed_ein", "proposed_bmf_name", "proposed_city",
                     "proposed_state", "method", "alternates"])
    for rank, (display, norm, city, state, p24, pall, funders) in enumerate(rows, 1):
        category = "daf_sponsor" if DAF_PATTERN.search(norm or "") else "org"
        proposals = propose(conn, norm or "", state or "")
        primary = proposals[0] if proposals else ("", "", "", "", "no_proposal")
        alternates = "; ".join(
            f"{p[0]}:{p[1][:40]}" for p in proposals[1:]) if len(proposals) > 1 else ""
        writer.writerow([
            rank, display, norm, city, state, p24, pall, funders, category,
            primary[0], primary[1], primary[2], primary[3], primary[4],
            alternates,
        ])
        if rank % 100 == 0:
            log(f"  {rank}/{len(rows)} probed")
    log("done")


if __name__ == "__main__":
    main()
