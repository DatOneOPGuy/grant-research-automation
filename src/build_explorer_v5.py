"""Build the Explorer v5 read model from the v5 identity + evidence ledger.

One query-optimized SQLite file (data/explorer_v5.db) serving the filter
product: paid grants only, tax years 2023-2024, honest identity and
classification status on every row. Rebuilt from scratch each run; the
pipeline database is opened read-only.
"""

from __future__ import annotations

import re
import sqlite3
import sys
import time
from pathlib import Path

PIPELINE_DB = Path("data/grants_v2.db")
BMF_DB = Path("data/bmf_registry.db")
OUT_DB = Path("data/explorer_v5.db")
CHRISTIAN = ("evangelical_protestant", "catholic", "orthodox_christian",
             "christian_unspecified")
AUTHORITATIVE = ("human", "ntee", "church_code_name", "group_exemption")
DAF_PATTERN = re.compile(
    r"\b(donor advised|charitable gift fund|giving fund|philanthropic tr(ust)?|"
    r"donors? trust|fidelity charitable|schwab charitable|vanguard charitable|"
    r"american online giving|national christian foundation|american endowment|"
    r"national philanthropic)\b")
TESTAMENTARY = re.compile(r"\b(tuw|tua|uw|testamentary|crut|crat|charitable remainder)\b")

SCHEMA = """
CREATE TABLE foundations (
    ein TEXT PRIMARY KEY, name TEXT, city TEXT, state TEXT,
    assets INTEGER, revenue INTEGER, website TEXT, phone TEXT,
    contact_person TEXT, contact_email TEXT,
    application_status TEXT, latest_tax_year INTEGER,
    paid_2324 INTEGER DEFAULT 0, grant_count_2324 INTEGER DEFAULT 0,
    recipient_count INTEGER DEFAULT 0, median_grant INTEGER,
    christian_dollars INTEGER DEFAULT 0, nonchristian_dollars INTEGER DEFAULT 0,
    unclassified_dollars INTEGER DEFAULT 0, daf_dollars INTEGER DEFAULT 0,
    coverage_pct REAL DEFAULT 0, coverage_band TEXT DEFAULT 'Low',
    is_testamentary INTEGER DEFAULT 0, is_micro INTEGER DEFAULT 0,
    active_2023 INTEGER DEFAULT 0, active_2024 INTEGER DEFAULT 0
);
CREATE TABLE tradition_stats (
    ein TEXT, tradition TEXT, tier TEXT,
    dollars INTEGER, recipients INTEGER,
    PRIMARY KEY (ein, tradition, tier)
);
CREATE TABLE recipient_states (
    ein TEXT, state TEXT, dollars INTEGER, PRIMARY KEY (ein, state));
CREATE TABLE recipients (
    entity_id TEXT PRIMARY KEY, ein TEXT, name TEXT,
    identity_status TEXT, tradition TEXT, method TEXT, confidence REAL,
    is_daf INTEGER DEFAULT 0, mission_text TEXT, website TEXT,
    total_received INTEGER DEFAULT 0, funder_count INTEGER DEFAULT 0
);
CREATE TABLE frs (
    ein TEXT, entity_id TEXT, dollars INTEGER, grants INTEGER,
    last_year INTEGER, PRIMARY KEY (ein, entity_id)
);
CREATE TABLE grants (
    id INTEGER PRIMARY KEY, funder_ein TEXT, entity_id TEXT,
    recipient_name TEXT, recipient_city TEXT, recipient_state TEXT,
    amount INTEGER, tax_year INTEGER, purpose TEXT
);
"""

INDEXES = """
CREATE INDEX idx_f_state ON foundations(state);
CREATE INDEX idx_f_paid ON foundations(paid_2324);
CREATE INDEX idx_f_app ON foundations(application_status);
CREATE INDEX idx_f_cov ON foundations(coverage_band);
CREATE INDEX idx_ts_lookup ON tradition_stats(tradition, tier, dollars);
CREATE INDEX idx_ts_ein ON tradition_stats(ein);
CREATE INDEX idx_rs_state ON recipient_states(state, dollars);
CREATE INDEX idx_r_name ON recipients(name);
CREATE INDEX idx_r_tradition ON recipients(tradition);
"""


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def open_dbs() -> tuple[sqlite3.Connection, str, str]:
    OUT_DB.unlink(missing_ok=True)
    # uri=True on the primary connection so the file: ATTACH URIs below are
    # parsed as URIs rather than literal filenames.
    out = sqlite3.connect(f"file:{OUT_DB.resolve()}", uri=True)
    out.executescript(SCHEMA)
    out.execute("ATTACH DATABASE ? AS p",
                (f"file:{PIPELINE_DB.resolve()}?mode=ro",))
    out.execute("ATTACH DATABASE ? AS bmf",
                (f"file:{BMF_DB.resolve()}?mode=ro",))
    run_id = out.execute(
        "SELECT run_id FROM p.identity_runs ORDER BY created_at_utc DESC LIMIT 1"
    ).fetchone()[0]
    release_id = out.execute(
        "SELECT release_id FROM p.classification_releases "
        "WHERE identity_run_id=? AND status='published' "
        "ORDER BY created_at_utc DESC LIMIT 1", (run_id,)).fetchone()[0]
    log(f"identity run {run_id} | classification release {release_id}")
    return out, run_id, release_id


def build_recipients(out: sqlite3.Connection, run_id: str, release_id: str) -> None:
    log("recipients: entities + resolutions + canonical mission text…")
    out.execute("""
        INSERT INTO recipients (entity_id, ein, name, identity_status,
                                tradition, method, confidence)
        SELECT e.entity_id, e.bmf_ein, e.canonical_name, e.identity_status,
               r.classification, ev.evidence_method, r.confidence
        FROM p.recipient_entities e
        LEFT JOIN p.classification_resolutions r
          ON r.release_id=? AND r.entity_id=e.entity_id
        LEFT JOIN p.classification_evidence ev ON ev.evidence_id=r.evidence_id
        WHERE e.run_id=?
    """, (release_id, run_id))
    # Canonical mission doc per EIN: latest tax year, amended preferred.
    out.execute("""
        CREATE TEMP TABLE best_doc AS
        SELECT ein, mission_text, website FROM (
          SELECT ein, mission_text, website,
                 ROW_NUMBER() OVER (PARTITION BY ein ORDER BY tax_year DESC,
                     is_amended DESC, object_id DESC) AS rn
          FROM p.r990_documents WHERE parse_status='parsed')
        WHERE rn=1
    """)
    out.execute("CREATE INDEX temp.idx_bd ON best_doc(ein)")
    out.execute("""
        UPDATE recipients SET
          mission_text=(SELECT mission_text FROM best_doc d WHERE d.ein=recipients.ein),
          website=(SELECT website FROM best_doc d WHERE d.ein=recipients.ein)
        WHERE ein IS NOT NULL
    """)
    for entity_id, name in out.execute(
            "SELECT entity_id, name FROM recipients").fetchall():
        if DAF_PATTERN.search((name or "").lower()):
            out.execute("UPDATE recipients SET is_daf=1 WHERE entity_id=?",
                        (entity_id,))
    out.commit()
    n, daf = out.execute(
        "SELECT COUNT(*), SUM(is_daf) FROM recipients").fetchone()
    log(f"recipients: {n:,} ({daf:,} DAF sponsors flagged)")


def build_grants(out: sqlite3.Connection, run_id: str) -> None:
    log("grants: paid 2023-2024 receipt rows…")
    out.execute("""
        INSERT INTO grants (funder_ein, entity_id, recipient_name,
                            recipient_city, recipient_state, amount,
                            tax_year, purpose)
        SELECT t.ein, em.entity_id, g.display_name, g.city, g.state,
               g.signed_amount, g.tax_year, t.purpose
        FROM p.grant_norm g
        JOIN p.grant_transactions t ON t.grant_id=g.grant_id
        JOIN p.recipient_entity_mentions em
          ON em.run_id=g.run_id AND em.mention_id=g.mention_id
        WHERE g.run_id=? AND g.tax_year IN (2023, 2024)
    """, (run_id,))
    out.commit()
    log(f"grants: {out.execute('SELECT COUNT(*) FROM grants').fetchone()[0]:,} rows")


def build_rollups(out: sqlite3.Connection) -> None:
    log("rollups: foundation x recipient, recipient totals, states…")
    # Index the receipt table before any GROUP BY / correlated pass over it.
    out.execute("CREATE INDEX idx_g_funder ON grants(funder_ein, tax_year)")
    out.execute("CREATE INDEX idx_g_entity ON grants(entity_id)")
    out.execute("""
        INSERT INTO frs
        SELECT funder_ein, entity_id, SUM(amount), COUNT(*), MAX(tax_year)
        FROM grants GROUP BY 1, 2
    """)
    # The correlated recipient-totals UPDATE needs this or it goes quadratic
    # over 1.3M recipients x 2.5M frs rows (the standing project lesson).
    out.execute("CREATE INDEX idx_frs_entity ON frs(entity_id)")
    out.execute("""
        UPDATE recipients SET
          total_received=COALESCE((SELECT SUM(dollars) FROM frs
                                   WHERE frs.entity_id=recipients.entity_id), 0),
          funder_count=COALESCE((SELECT COUNT(*) FROM frs
                                 WHERE frs.entity_id=recipients.entity_id), 0)
    """)
    out.execute("""
        INSERT INTO recipient_states
        SELECT funder_ein, recipient_state, SUM(amount) FROM grants
        WHERE recipient_state != '' GROUP BY 1, 2
    """)
    out.commit()


def build_foundations(out: sqlite3.Connection) -> None:
    log("foundations: base facts from canonical filings…")
    out.execute("""
        INSERT INTO foundations (ein, name, city, state, assets, revenue,
            website, phone, contact_person, contact_email,
            application_status, latest_tax_year)
        SELECT f.ein, f.organization_name, f.city, f.state, f.assets_eoy,
               f.total_revenue, f.website, f.phone, f.contact_person,
               f.contact_email,
               CASE WHEN f.invite_only=1 THEN 'Invite Only'
                    WHEN COALESCE(f.application_format,'') != ''
                      OR COALESCE(f.deadlines,'') != ''
                      OR COALESCE(f.restrictions,'') != ''
                      THEN 'Accepting Applications'
                    WHEN COALESCE(f.contact_person,'') != ''
                      OR COALESCE(f.contact_email,'') != ''
                      THEN 'Contact First'
                    ELSE 'Unknown' END,
               f.tax_year
        FROM p.foundation_filings f
        JOIN (SELECT ein, MAX(tax_year) AS ty FROM p.canonical_filings
              GROUP BY ein) latest
          ON latest.ein=f.ein AND latest.ty=f.tax_year
        JOIN p.canonical_filings c ON c.ein=f.ein AND c.tax_year=f.tax_year
          AND c.object_id=f.object_id
    """)
    out.commit()
    log("foundations: giving aggregates + tradition stats + coverage…")
    out.execute("""
        CREATE TEMP TABLE agg AS
        SELECT g.funder_ein AS ein,
          SUM(g.amount) AS paid, COUNT(*) AS n,
          COUNT(DISTINCT g.entity_id) AS recips,
          MAX(CASE WHEN g.tax_year=2023 THEN 1 ELSE 0 END) AS a23,
          MAX(CASE WHEN g.tax_year=2024 THEN 1 ELSE 0 END) AS a24,
          SUM(CASE WHEN r.is_daf=1 THEN g.amount ELSE 0 END) AS daf,
          SUM(CASE WHEN r.is_daf=0 AND r.tradition IN
                ('evangelical_protestant','catholic','orthodox_christian',
                 'christian_unspecified') THEN g.amount ELSE 0 END) AS chr,
          SUM(CASE WHEN r.is_daf=0 AND r.tradition IN
                ('jewish','muslim','mormon_lds','christian_science',
                 'other_religion','secular','nonchristian_unspecified')
              THEN g.amount ELSE 0 END) AS nonchr
        FROM grants g JOIN recipients r ON r.entity_id=g.entity_id
        GROUP BY 1
    """)
    out.execute("CREATE INDEX temp.idx_agg ON agg(ein)")
    out.execute("""
        UPDATE foundations SET
          paid_2324=COALESCE((SELECT paid FROM agg WHERE agg.ein=foundations.ein),0),
          grant_count_2324=COALESCE((SELECT n FROM agg WHERE agg.ein=foundations.ein),0),
          recipient_count=COALESCE((SELECT recips FROM agg WHERE agg.ein=foundations.ein),0),
          active_2023=COALESCE((SELECT a23 FROM agg WHERE agg.ein=foundations.ein),0),
          active_2024=COALESCE((SELECT a24 FROM agg WHERE agg.ein=foundations.ein),0),
          daf_dollars=COALESCE((SELECT daf FROM agg WHERE agg.ein=foundations.ein),0),
          christian_dollars=COALESCE((SELECT chr FROM agg WHERE agg.ein=foundations.ein),0),
          nonchristian_dollars=COALESCE((SELECT nonchr FROM agg WHERE agg.ein=foundations.ein),0)
    """)
    out.execute("""
        UPDATE foundations SET
          unclassified_dollars = paid_2324 - christian_dollars
                                 - nonchristian_dollars - daf_dollars,
          coverage_pct = CASE WHEN paid_2324 > 0 THEN
            ROUND(100.0 * (christian_dollars + nonchristian_dollars
                           + daf_dollars) / paid_2324, 1) ELSE 0 END
    """)
    out.execute("""
        UPDATE foundations SET
          coverage_band = CASE WHEN coverage_pct >= 80 THEN 'High'
                               WHEN coverage_pct >= 50 THEN 'Moderate'
                               ELSE 'Low' END,
          is_micro = CASE WHEN paid_2324 < 50000 THEN 1 ELSE 0 END
    """)
    for ein, name in out.execute(
            "SELECT ein, name FROM foundations").fetchall():
        if TESTAMENTARY.search(f" {(name or '').lower()} "):
            out.execute(
                "UPDATE foundations SET is_testamentary=1 WHERE ein=?", (ein,))
    out.commit()


def build_tradition_stats(out: sqlite3.Connection) -> None:
    log("tradition stats (authoritative and any tiers)…")
    for tier, method_filter in (
        ("authoritative",
         "r.method IN ('human','ntee','church_code_name','group_exemption')"),
        ("any", "r.tradition IS NOT NULL"),
    ):
        out.execute(f"""
            INSERT OR REPLACE INTO tradition_stats
            SELECT f.ein, r.tradition, '{tier}', SUM(f.dollars), COUNT(*)
            FROM frs f JOIN recipients r ON r.entity_id=f.entity_id
            WHERE {method_filter} AND r.is_daf=0
            GROUP BY 1, 2
        """)
    out.execute("""
        INSERT OR REPLACE INTO tradition_stats
        SELECT f.ein, 'unclassified', 'any', SUM(f.dollars), COUNT(*)
        FROM frs f JOIN recipients r ON r.entity_id=f.entity_id
        WHERE r.tradition IS NULL GROUP BY 1
    """)
    out.commit()


def median_grants(out: sqlite3.Connection) -> None:
    log("median grant per foundation (streaming)…")
    current, amounts, updates = None, [], []
    for ein, amount in out.execute(
            "SELECT funder_ein, amount FROM grants ORDER BY funder_ein"):
        if ein != current:
            if current is not None and amounts:
                amounts.sort()
                updates.append((amounts[len(amounts) // 2], current))
            current, amounts = ein, []
        amounts.append(amount)
    if current is not None and amounts:
        amounts.sort()
        updates.append((amounts[len(amounts) // 2], current))
    out.executemany("UPDATE foundations SET median_grant=? WHERE ein=?", updates)
    out.commit()


def main() -> None:
    started = time.monotonic()
    out, run_id, release_id = open_dbs()
    build_recipients(out, run_id, release_id)
    build_grants(out, run_id)
    build_rollups(out)
    build_foundations(out)
    build_tradition_stats(out)
    median_grants(out)
    log("indexing…")
    out.executescript(INDEXES)
    out.execute("PRAGMA main.optimize")
    out.commit()
    stats = {
        "foundations": out.execute("SELECT COUNT(*) FROM foundations").fetchone()[0],
        "with 23-24 giving": out.execute(
            "SELECT COUNT(*) FROM foundations WHERE paid_2324>0").fetchone()[0],
        "recipients": out.execute("SELECT COUNT(*) FROM recipients").fetchone()[0],
        "grants": out.execute("SELECT COUNT(*) FROM grants").fetchone()[0],
        "paid $": out.execute("SELECT SUM(paid_2324) FROM foundations").fetchone()[0],
        "christian $": out.execute(
            "SELECT SUM(christian_dollars) FROM foundations").fetchone()[0],
        "unclassified $": out.execute(
            "SELECT SUM(unclassified_dollars) FROM foundations").fetchone()[0],
        "with mission text": out.execute(
            "SELECT COUNT(*) FROM recipients WHERE mission_text!=''").fetchone()[0],
    }
    for key, value in stats.items():
        log(f"  {key}: {value:,}")
    log(f"done in {time.monotonic() - started:,.0f}s -> {OUT_DB}")


if __name__ == "__main__":
    main()
