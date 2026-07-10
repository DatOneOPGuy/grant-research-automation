"""Recipient knowledge base: establish each grant recipient once.

Every distinct grantee gets free seed/rule tags first; the separate local
Ollama pipeline handles only recipients left unresolved by those methods.
"""

import json
import logging
import re
import sqlite3

from src.config import DB_PATH
from src.faith_config import RULE_PATTERNS, SEED_RECIPIENTS
from src.matcher import normalize

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

_RULES = [(re.compile(pat), tags) for pat, tags in RULE_PATTERNS]


def ensure_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recipients (
            name_norm TEXT PRIMARY KEY,
            display_name TEXT,
            tags TEXT,
            source TEXT,
            max_grant INTEGER
        )
    """)


def rule_tags(name: str) -> list[dict]:
    """High-precision name-pattern tags; free, applied to every grant."""
    lower = name.lower()
    tags = {}
    for pattern, tag_names in _RULES:
        if pattern.search(lower):
            for t in tag_names:
                tags[t] = 100
    return [{'name': t, 'confidence': c} for t, c in tags.items()]


def build_knowledge_base(conn: sqlite3.Connection):
    """Populate recipients from grants; tag via seeds then rules."""
    ensure_table(conn)
    seeds = {
        normalize(name): [{'name': t, 'confidence': 100} for t in tags]
        for name, tags in SEED_RECIPIENTS.items()
    }

    rows = conn.execute(
        "SELECT grantee_name, MAX(amount) FROM grants "
        "WHERE grantee_name != '' GROUP BY grantee_name"
    ).fetchall()
    log.info("Distinct raw grantee names: %d", len(rows))

    # Collapse raw names to normalized form, keeping the largest grant
    collapsed: dict[str, tuple[str, int]] = {}
    for raw_name, max_amt in rows:
        norm = normalize(raw_name)
        if not norm:
            continue
        prev = collapsed.get(norm)
        if prev is None or (max_amt or 0) > prev[1]:
            collapsed[norm] = (raw_name, max_amt or 0)
    log.info("Normalized distinct recipients: %d", len(collapsed))

    counts = {'seed': 0, 'rule': 0, 'pending': 0}
    columns = {row[1] for row in conn.execute("PRAGMA table_info(recipients)")}
    protects_llm = 'classification_method' in columns
    for norm, (raw_name, max_amt) in collapsed.items():
        if norm in seeds:
            tags, source = seeds[norm], 'seed'
        else:
            tags = rule_tags(raw_name)
            source = 'rule' if tags else 'pending'
        counts[source] += 1
        if protects_llm:
            conn.execute(
                """INSERT INTO recipients (name_norm, display_name, tags, source, max_grant)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(name_norm) DO UPDATE SET
                     display_name=excluded.display_name,
                     max_grant=excluded.max_grant,
                     tags=CASE WHEN recipients.classification_method IN ('llm', 'llm_failed')
                               THEN recipients.tags ELSE excluded.tags END,
                     source=CASE WHEN recipients.classification_method IN ('llm', 'llm_failed')
                                 THEN recipients.source ELSE excluded.source END""",
                (norm, raw_name, json.dumps(tags), source, max_amt),
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO recipients "
                "(name_norm, display_name, tags, source, max_grant) "
                "VALUES (?, ?, ?, ?, ?)",
                (norm, raw_name, json.dumps(tags), source, max_amt),
            )
    conn.commit()
    log.info("Knowledge base: %(seed)d seeded, %(rule)d rule-tagged, "
             "%(pending)d pending LLM", counts)


def run():
    conn = sqlite3.connect(DB_PATH)
    build_knowledge_base(conn)
    conn.close()
    log.info("Rule/seed knowledge base refreshed. Run "
             "python3 -m src.local_recipient_classification for local Ollama work.")


if __name__ == '__main__':
    run()
