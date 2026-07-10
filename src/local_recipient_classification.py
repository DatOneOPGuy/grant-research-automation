"""Restartable local Ollama classification for unresolved grant recipients.

SQLite is the durable checkpoint: only rows still pending are selected after a
restart. The JSON file is a bounded, atomic last-commit journal, not a growing
in-memory index of every processed recipient.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from src.recipient_batching import run_batches
from src.recipient_taxonomy import (
    DEFAULT_MODEL,
    TAXONOMY,
    infer_legacy_tradition,
)


BATCH_SIZE = 500
MAX_ATTEMPTS = 3
DEFAULT_DB_PATH = Path("data/grants.db")
DEFAULT_CHECKPOINT_PATH = Path("data/classification_checkpoint.json")
PENDING_QUERY = """
SELECT name_norm, display_name, recipient_city, recipient_state,
       sample_purpose_text, classification_attempts
FROM recipients
WHERE source = 'pending'
  AND (tags IS NULL OR tags = '[]')
  AND (faith_classification IS NULL OR faith_classification = 'pending')
  AND (classification_method IS NULL OR classification_method NOT IN ('rule', 'ntee', 'llm', 'llm_failed'))
  AND COALESCE(classification_attempts, 0) < 3
  AND COALESCE(max_grant, 0) >= 5000;
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-attempts", type=int, default=MAX_ATTEMPTS)
    parser.add_argument("--prepare", action="store_true",
                        help="Apply additive schema/provenance migration only.")
    return parser.parse_args()


def open_connection(db_path: Path) -> sqlite3.Connection:
    """Use WAL and NORMAL sync to avoid fsync-heavy transaction latency."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Add provenance/context columns without modifying existing recipient data."""
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(recipients)")
    }
    additions = {
        "faith_classification": "TEXT",
        "classification_method": "TEXT",
        "confidence_score": "REAL",
        "classification_reason": "TEXT",
        "classification_attempts": "INTEGER NOT NULL DEFAULT 0",
        "recipient_city": "TEXT",
        "recipient_state": "TEXT",
        "sample_purpose_text": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE recipients ADD COLUMN {name} {definition}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_recipients_llm_pending "
        "ON recipients(source, classification_method, faith_classification) "
        "WHERE source = 'pending'"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_grants_grantee_name "
        "ON grants(grantee_name)"
    )
    conn.commit()


def migrate_legacy_provenance(conn: sqlite3.Connection) -> dict[str, int]:
    """Method-tag existing rule/NTEE records and recover traditions when safe."""
    method_updates = conn.execute(
        """UPDATE recipients
           SET classification_method = CASE
               WHEN source IN ('rule', 'rulev2', 'rulev2_excl', 'seed') THEN 'rule'
               WHEN source IN ('ntee', 'ntee_excl') THEN 'ntee'
           END
           WHERE classification_method IS NULL
             AND source IN ('rule', 'rulev2', 'rulev2_excl', 'seed', 'ntee', 'ntee_excl')"""
    ).rowcount
    updates: list[tuple[str, str]] = []
    rows = conn.execute(
        """SELECT name_norm, display_name
           FROM recipients
           WHERE faith_classification IS NULL
             AND classification_method IN ('rule', 'ntee')"""
    )
    for name_norm, display_name in rows:
        tradition = infer_legacy_tradition(display_name or "")
        if tradition in TAXONOMY:
            updates.append((tradition, name_norm))
    conn.executemany(
        "UPDATE recipients SET faith_classification = ? WHERE name_norm = ?",
        updates,
    )
    conn.commit()
    return {"method_tagged": max(method_updates, 0), "traditions_recovered": len(updates)}


def print_preflight(conn: sqlite3.Connection) -> None:
    """Show exactly what is protected and what remains eligible for LLM work."""
    rows = conn.execute(
        """SELECT COALESCE(classification_method, 'unassigned'), COUNT(*)
           FROM recipients GROUP BY classification_method ORDER BY 1"""
    ).fetchall()
    pending = conn.execute(
        """SELECT COUNT(*) FROM recipients
           WHERE source = 'pending' AND (tags IS NULL OR tags = '[]')
             AND (faith_classification IS NULL OR faith_classification = 'pending')
             AND (classification_method IS NULL OR classification_method NOT IN ('rule', 'ntee', 'llm', 'llm_failed'))
             AND COALESCE(classification_attempts, 0) < 3 AND COALESCE(max_grant, 0) >= 5000"""
    ).fetchone()[0]
    print("Classification provenance:")
    for method, count in rows:
        print(f"  {method}: {count:,}")
    print(f"Eligible for local LLM pass ($5k+): {pending:,}")


def run_classifier(args: argparse.Namespace) -> None:
    """Read strict 500-record pandas chunks and classify only unresolved rows."""
    checkpoint_path = DEFAULT_CHECKPOINT_PATH
    with open_connection(args.db) as conn:
        ensure_schema(conn)
        migration = migrate_legacy_provenance(conn)
        print(f"Migration: {migration['method_tagged']:,} methods tagged; "
              f"{migration['traditions_recovered']:,} traditions recovered.")
        print_preflight(conn)
        if args.prepare:
            return
        run_batches(conn, PENDING_QUERY, args.model, args.max_attempts, checkpoint_path)


def main() -> None:
    args = parse_args()
    if not args.db.exists():
        raise FileNotFoundError(f"SQLite database not found: {args.db}")
    if args.max_attempts < 1:
        raise ValueError("--max-attempts must be at least 1")
    run_classifier(args)


if __name__ == "__main__":
    main()
