"""Prep for mission-text classification: target population + gold candidates.

Builds a canonical-mission-per-EIN table, the classification target set
(matched entities that are currently UNCLASSIFIED and have mission text), and
a stratified gold-candidate sample covering the hard cases the run must get
right. Read-only against identity/ledger tables; writes only its own
mission_* tables into grants_v2.db.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

DB = Path("data/grants_v2.db")
GOLD_JSON = Path("logs/gold_candidates.json")
PER_STRATUM = 45

SCHEMA = """
DROP TABLE IF EXISTS mission_canonical;
CREATE TABLE mission_canonical AS
SELECT ein, object_id, tax_year, mission_text, program_texts_json
FROM (
  SELECT ein, object_id, tax_year, mission_text, program_texts_json,
         ROW_NUMBER() OVER (PARTITION BY ein
           ORDER BY tax_year DESC, is_amended DESC, object_id DESC) AS rn
  FROM r990_documents
  WHERE parse_status='parsed' AND COALESCE(mission_text,'') != ''
) WHERE rn=1;
CREATE INDEX idx_mc_ein ON mission_canonical(ein);
"""

# Stratum heuristics run on lower-cased "name || ' ' || mission_text".
STRATA = [
    ("christian_obvious", re.compile(
        r"\b(gospel|jesus|jesus christ|christ|ministr|disciple|church plant|"
        r"evangel|savior|biblical|great commission|kingdom of god|missionary|"
        r"christian faith|for christ)\b")),
    ("catholic", re.compile(
        r"\b(catholic|diocese|parish|archdiocese|newman|jesuit|franciscan|"
        r"vincent de paul|knights of columbus|our lady|holy cross)\b")),
    ("jewish", re.compile(
        r"\b(jewish|synagogue|torah|hebrew|yeshiva|chabad|judaism|kosher|"
        r"b nai|congregation beth|jcc)\b")),
    ("muslim", re.compile(r"\b(muslim|islamic|mosque|masjid|quran|islam)\b")),
    ("faith_adjacent_secular", re.compile(
        r"\b(hospital|health system|medical center|university|college|"
        r"academy|school)\b")),
    ("boilerplate", re.compile(
        r"^.{0,55}$|to support (the )?(community|charitable|various)|"
        r"charitable purposes|for the benefit of|general charitable")),
]
FAITH_NAME = re.compile(
    r"\b(saint|st|christian|catholic|christ|baptist|methodist|lutheran|"
    r"presbyterian|jewish|hebrew|gospel|grace|faith|trinity|calvary)\b")


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def latest_ids(conn: sqlite3.Connection) -> tuple[str, str]:
    run = conn.execute(
        "SELECT run_id FROM identity_runs ORDER BY created_at_utc DESC LIMIT 1"
    ).fetchone()[0]
    rel = conn.execute(
        "SELECT release_id FROM classification_releases WHERE status='published' "
        "ORDER BY created_at_utc DESC LIMIT 1").fetchone()[0]
    return run, rel


def _helper_tables(conn: sqlite3.Connection, run_id: str, release_id: str) -> None:
    """Precompute PK-indexed entity sets so the big joins use index probes
    instead of scanning materialized subqueries per row (the plan showed
    250k x 250k full scans — the recurring unindexed-join hazard)."""
    log("  building indexed helper tables (rule / resolved / paid)…")
    conn.executescript("""
        DROP TABLE IF EXISTS _rule_ents;
        DROP TABLE IF EXISTS _resolved_ents;
        DROP TABLE IF EXISTS _paid_ents;
        CREATE TABLE _rule_ents (entity_id TEXT PRIMARY KEY);
        CREATE TABLE _resolved_ents (entity_id TEXT PRIMARY KEY);
        CREATE TABLE _paid_ents (entity_id TEXT PRIMARY KEY, paid INTEGER);
    """)
    conn.execute(
        "INSERT OR IGNORE INTO _rule_ents SELECT DISTINCT entity_id "
        "FROM classification_evidence WHERE identity_run_id=? "
        "AND evidence_method='rule'", (run_id,))
    conn.execute(
        "INSERT OR IGNORE INTO _resolved_ents SELECT entity_id "
        "FROM classification_resolutions WHERE release_id=?", (release_id,))
    conn.execute(
        "INSERT INTO _paid_ents SELECT em.entity_id, SUM(mm.paid_dollars) "
        "FROM recipient_entity_mentions em JOIN recipient_mentions mm "
        "ON mm.run_id=em.run_id AND mm.mention_id=em.mention_id "
        "WHERE em.run_id=? GROUP BY em.entity_id", (run_id,))
    conn.commit()


def build_targets(conn: sqlite3.Connection, run_id: str, release_id: str) -> None:
    log("building mission_targets (matched, unclassified, has mission text)…")
    _helper_tables(conn, run_id, release_id)
    conn.executescript("""
        DROP TABLE IF EXISTS mission_targets;
        CREATE TABLE mission_targets (
            entity_id TEXT PRIMARY KEY, ein TEXT, name TEXT,
            mission_text TEXT, program_texts_json TEXT,
            paid_dollars INTEGER, is_name_neutral INTEGER
        );
    """)
    conn.execute("""
        INSERT INTO mission_targets
        SELECT e.entity_id, e.bmf_ein, e.canonical_name,
               m.mission_text, m.program_texts_json,
               COALESCE(p.paid, 0),
               CASE WHEN rl.entity_id IS NULL THEN 1 ELSE 0 END
        FROM recipient_entities e
        JOIN mission_canonical m ON m.ein = e.bmf_ein
        LEFT JOIN _rule_ents rl ON rl.entity_id = e.entity_id
        LEFT JOIN _paid_ents p ON p.entity_id = e.entity_id
        LEFT JOIN _resolved_ents rs ON rs.entity_id = e.entity_id
        WHERE e.run_id=? AND e.identity_status='matched_bmf'
          AND rs.entity_id IS NULL
    """, (run_id,))
    conn.commit()
    n, dollars, neutral = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(paid_dollars),0), SUM(is_name_neutral) "
        "FROM mission_targets").fetchone()
    log(f"  targets: {n:,} entities | ${dollars/1e9:.2f}B paid "
        f"| {neutral:,} name-neutral")


def stratified_gold(conn: sqlite3.Connection, run_id: str) -> None:
    """Sample gold candidates from the FULL matched population (classified or
    not) so the gold set spans traditions and hard cases, not just gaps."""
    log("sampling stratified gold candidates across the full matched space…")
    rows = conn.execute("""
        SELECT e.entity_id, e.canonical_name, e.bmf_ein,
               m.mission_text, COALESCE(p.paid, 0) AS paid
        FROM recipient_entities e
        JOIN mission_canonical m ON m.ein=e.bmf_ein
        LEFT JOIN _paid_ents p ON p.entity_id=e.entity_id
        WHERE e.run_id=? AND e.identity_status='matched_bmf'
    """, (run_id,)).fetchall()
    log(f"  {len(rows):,} matched entities with mission text to stratify")
    # Deterministic pseudo-shuffle by entity_id hash so re-runs are stable.
    rows.sort(key=lambda r: r[0])
    buckets: dict[str, list] = {name: [] for name, _ in STRATA}
    buckets["secular_obvious"] = []
    seen: set[str] = set()
    for entity_id, name, ein, mission, paid in rows:
        blob = f"{name} {mission}".lower()
        placed = None
        for stratum, pattern in STRATA:
            if stratum == "faith_adjacent_secular":
                # Only a hard case if the NAME sounds faith-y but it's an
                # institution — that is the ambiguous population.
                if pattern.search(blob) and FAITH_NAME.search((name or "").lower()):
                    placed = stratum
                    break
                continue
            if pattern.search(blob):
                placed = stratum
                break
        if placed is None:
            placed = "secular_obvious"
        if len(buckets[placed]) < PER_STRATUM and entity_id not in seen:
            buckets[placed].append({
                "entity_id": entity_id, "name": name, "ein": ein,
                "mission_text": mission, "paid_dollars": paid,
                "stratum_hint": placed,
            })
            seen.add(entity_id)
    sample = [item for items in buckets.values() for item in items]
    GOLD_JSON.parent.mkdir(exist_ok=True)
    GOLD_JSON.write_text(json.dumps(sample, indent=1))
    for stratum, items in buckets.items():
        log(f"  {stratum}: {len(items)}")
    log(f"  wrote {len(sample)} gold candidates -> {GOLD_JSON}")


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)
    run_id, release_id = latest_ids(conn)
    log(f"identity {run_id} | release {release_id}")
    build_targets(conn, run_id, release_id)
    stratified_gold(conn, run_id)
    conn.close()


if __name__ == "__main__":
    main()
