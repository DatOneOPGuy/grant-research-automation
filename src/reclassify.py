"""Apply the expanded rule classifier to untagged recipients.

Additive: existing seed/rule tags are preserved; only 'pending' (untagged)
recipients are classified. Christian -> 'Christian Ministry' tag;
non-Christian -> 'Non-Christian' marker (raises coverage without inflating
the Christian percentage).
"""

import json
import logging
import sqlite3

from src.classifier import classify
from src.config import DB_PATH

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

CHRISTIAN_TAG = json.dumps([{'name': 'Christian Ministry', 'confidence': 85}])
NONCHRISTIAN_TAG = json.dumps([{'name': 'Non-Christian', 'confidence': 85}])


def run():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT name_norm, display_name FROM recipients "
        "WHERE (tags = '[]' OR tags IS NULL)"
    ).fetchall()
    log.info("Classifying %d untagged recipients...", len(rows))

    chr_n = non_n = 0
    for norm, display in rows:
        c = classify(display)
        if c == 'christian':
            conn.execute(
                "UPDATE recipients SET tags = ?, source = 'rulev2' "
                "WHERE name_norm = ?", (CHRISTIAN_TAG, norm))
            chr_n += 1
        elif c == 'nonchristian':
            conn.execute(
                "UPDATE recipients SET tags = ?, source = 'rulev2_excl' "
                "WHERE name_norm = ?", (NONCHRISTIAN_TAG, norm))
            non_n += 1
    conn.commit()
    stats = conn.execute(
        "SELECT SUM(tags != '[]' AND tags IS NOT NULL), COUNT(*) "
        "FROM recipients"
    ).fetchone()
    conn.close()
    log.info("Newly classified: %d Christian, %d non-Christian. "
             "Total tagged now %d / %d recipients", chr_n, non_n, *stats)


if __name__ == '__main__':
    run()
