"""Recipient knowledge base: classify each grant recipient once.

Every distinct grantee gets tags exactly once (seed -> rule -> LLM, in
cost order); every foundation that ever funded it inherits the tags.
LLM classification is limited to recipients with at least one grant of
CLASSIFY_MIN_GRANT ($5k) and cached on disk, so re-runs are free.
"""

import json
import logging
import os
import re
import sqlite3

from src.config import DB_PATH
from src.faith_config import (
    ALL_TAGS, CACHE_PATH, CLASSIFY_BATCH_SIZE, CLASSIFY_MIN_GRANT,
    CLASSIFY_MODEL, RULE_PATTERNS, SEED_RECIPIENTS,
)
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
    for norm, (raw_name, max_amt) in collapsed.items():
        if norm in seeds:
            tags, source = seeds[norm], 'seed'
        else:
            tags = rule_tags(raw_name)
            source = 'rule' if tags else 'pending'
        counts[source] += 1
        conn.execute(
            "INSERT OR REPLACE INTO recipients "
            "(name_norm, display_name, tags, source, max_grant) "
            "VALUES (?, ?, ?, ?, ?)",
            (norm, raw_name, json.dumps(tags), source, max_amt),
        )
    conn.commit()
    log.info("Knowledge base: %(seed)d seeded, %(rule)d rule-tagged, "
             "%(pending)d pending LLM", counts)


def _load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def _classify_batch(client, batch: list[str]) -> dict:
    """One API call classifying a batch of recipient names."""
    listing = '\n'.join(f'{i + 1}. {n}' for i, n in enumerate(batch))
    prompt = (
        "You are classifying nonprofit organizations by name. For each "
        "organization below, return tags ONLY from this fixed list:\n"
        f"{', '.join(ALL_TAGS)}\n\n"
        "Return a JSON array; element i corresponds to organization i+1: "
        '[{"name": "<org name>", "tags": '
        '[{"name": "<tag>", "confidence": 0-100}]}]\n'
        "Use an empty tags array when nothing applies or you are unsure. "
        "Only include tags you are confident about.\n\n"
        f"Organizations:\n{listing}"
    )
    resp = client.messages.create(
        model=CLASSIFY_MODEL,
        max_tokens=4096,
        messages=[{'role': 'user', 'content': prompt}],
    )
    text = resp.content[0].text
    start, end = text.find('['), text.rfind(']') + 1
    results = json.loads(text[start:end])
    valid = set(ALL_TAGS)
    out = {}
    for name, item in zip(batch, results):
        tags = [t for t in item.get('tags', [])
                if t.get('name') in valid]
        out[name] = tags
    return out


def classify_pending(conn: sqlite3.Connection, limit: int | None = None):
    """LLM-classify pending recipients with a $5k+ grant. Cached."""
    if not os.environ.get('ANTHROPIC_API_KEY'):
        log.warning("ANTHROPIC_API_KEY not set — skipping LLM pass. "
                    "Rule/seed tags remain in effect.")
        return 0
    import anthropic
    client = anthropic.Anthropic()

    rows = conn.execute(
        "SELECT name_norm, display_name FROM recipients "
        "WHERE source = 'pending' AND max_grant >= ? "
        "ORDER BY max_grant DESC" + (f" LIMIT {int(limit)}" if limit else ""),
        (CLASSIFY_MIN_GRANT,),
    ).fetchall()
    cache = _load_cache()
    log.info("LLM classification: %d recipients (%d cached)",
             len(rows), sum(1 for _, d in rows if d in cache))

    done = 0
    todo = [(n, d) for n, d in rows if d not in cache]
    for i in range(0, len(todo), CLASSIFY_BATCH_SIZE):
        batch = todo[i:i + CLASSIFY_BATCH_SIZE]
        try:
            results = _classify_batch(client, [d for _, d in batch])
        except Exception as e:
            log.error("Batch failed at %d: %s", i, e)
            break
        cache.update(results)
        with open(CACHE_PATH, 'w') as f:
            json.dump(cache, f)
        done += len(batch)
        if done % 200 == 0:
            log.info("  classified %d / %d", done, len(todo))

    applied = 0
    for norm, display in rows:
        if display in cache:
            conn.execute(
                "UPDATE recipients SET tags = ?, source = 'llm' "
                "WHERE name_norm = ?",
                (json.dumps(cache[display]), norm),
            )
            applied += 1
    conn.commit()
    log.info("Applied LLM tags to %d recipients", applied)
    return applied


def run():
    conn = sqlite3.connect(DB_PATH)
    build_knowledge_base(conn)
    classify_pending(conn)
    conn.close()


if __name__ == '__main__':
    run()
