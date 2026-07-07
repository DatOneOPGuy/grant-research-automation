"""Database layer for Foundation Explorer.

Two databases, both effectively read-only for app queries:
- explorer.db: built once from foundation_database.csv (all 139,965
  universe rows with precomputed faith/application columns) + indexes.
- grants.db: the pipeline database, ATTACHed read-only (mode=ro) for
  grants, charitable activities, recipients, and raw foundation rows.
"""

import csv
import logging
import os
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
GRANTS_DB = Path(os.environ.get('GRANTS_DB', ROOT / 'data' / 'grants.db'))
EXPLORER_DB = Path(os.environ.get('EXPLORER_DB',
                                  ROOT / 'data' / 'explorer.db'))
UNIVERSE_CSV = Path(os.environ.get('UNIVERSE_CSV',
                                   ROOT / 'foundation_database.csv'))

NUMERIC_COLS = {
    'revenue', 'assets', 'distributions', 'faith_alignment_score',
    'christian_giving_pct', 'years_of_faith_giving', 'total_giving',
    'faith_giving', 'latest_tax_year', 'faith_score_composite',
    'christian_dollars_3yr', 'christian_dollars_2023',
    'christian_dollars_2024', 'christian_dollars_2025',
    'christian_grant_count_3yr', 'is_testamentary_trust', 'is_small_fund',
    'is_actively_giving', 'total_giving_3yr', 'nonchristian_dollars_3yr',
    'unclassified_dollars_3yr', 'classification_coverage',
    'christian_pct_floor', 'christian_pct_ceiling',
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_u_ein ON universe(ein)",
    "CREATE INDEX IF NOT EXISTS idx_u_state ON universe(state)",
    "CREATE INDEX IF NOT EXISTS idx_u_score "
    "ON universe(faith_alignment_score)",
    "CREATE INDEX IF NOT EXISTS idx_u_composite "
    "ON universe(faith_score_composite)",
    "CREATE INDEX IF NOT EXISTS idx_u_cd ON universe(christian_dollars_3yr)",
    "CREATE INDEX IF NOT EXISTS idx_u_dist ON universe(distributions)",
    "CREATE INDEX IF NOT EXISTS idx_u_status "
    "ON universe(application_status)",
    "CREATE INDEX IF NOT EXISTS idx_u_name ON universe(foundation_name)",
]

GRANTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_grants_year ON grants(tax_year)",
    "CREATE INDEX IF NOT EXISTS idx_grants_amount ON grants(amount)",
]


def build_explorer_db():
    """(Re)build explorer.db from foundation_database.csv if stale."""
    if (EXPLORER_DB.exists()
            and EXPLORER_DB.stat().st_mtime >= UNIVERSE_CSV.stat().st_mtime):
        return
    log.info("Building %s from %s ...", EXPLORER_DB, UNIVERSE_CSV)
    tmp = EXPLORER_DB.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    with UNIVERSE_CSV.open(newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        cols = ', '.join(
            f'"{c}" {"REAL" if c in NUMERIC_COLS else "TEXT"}'
            for c in header
        )
        conn.execute(f"CREATE TABLE universe ({cols})")
        placeholders = ', '.join('?' * len(header))
        conn.executemany(
            f"INSERT INTO universe VALUES ({placeholders})",
            (
                [None if v == '' else v for v in row]
                for row in reader
            ),
        )
    for idx in INDEXES:
        conn.execute(idx)
    conn.commit()
    conn.close()
    tmp.replace(EXPLORER_DB)
    log.info("explorer.db built")


def ensure_grants_indexes():
    """Safe additive indexes on the pipeline DB (spec-approved)."""
    conn = sqlite3.connect(GRANTS_DB)
    for idx in GRANTS_INDEXES:
        conn.execute(idx)
    conn.commit()
    conn.close()


def get_conn() -> sqlite3.Connection:
    """Connection with universe + read-only pipeline DB attached."""
    conn = sqlite3.connect(f"file:{EXPLORER_DB}?mode=ro", uri=True)
    conn.execute(
        f"ATTACH DATABASE 'file:{GRANTS_DB}?mode=ro' AS pipeline"
    )
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]
