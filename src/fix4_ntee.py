"""Fix 4: classify remaining unknown recipients via IRS BMF NTEE codes.

Builds a normalized-name -> NTEE lookup from the Business Master File and
applies authoritative IRS religion codes to still-unclassified recipients:
  X20 Christian / X21 Protestant / X22 Roman Catholic  -> christian
  X30 Jewish / X40 Islamic / X50 Buddhist / X70 Hindu   -> non-christian
Only religion (X) codes are used, for precision. Free, no LLM.
"""

import json
import logging
import sqlite3
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR, DB_PATH
from src.matcher import normalize

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

BMF_DIR = Path(DATA_DIR) / 'bmf'
CHRISTIAN_NTEE = ('X20', 'X21', 'X22', 'X24', 'X80', 'X81', 'X82', 'X83')
NONCHRISTIAN_NTEE = ('X30', 'X40', 'X50', 'X70')
CHRISTIAN_TAG = json.dumps([{'name': 'Christian Ministry', 'confidence': 90}])
NONCHRISTIAN_TAG = json.dumps([{'name': 'Non-Christian', 'confidence': 90}])


def build_ntee_lookup() -> dict[str, str]:
    lookup = {}
    for path in BMF_DIR.glob('eo*.csv'):
        df = pd.read_csv(path, usecols=['NAME', 'NTEE_CD'], dtype=str,
                         low_memory=False)
        df = df[df['NTEE_CD'].str.startswith('X', na=False)]
        for name, ntee in zip(df['NAME'], df['NTEE_CD']):
            norm = normalize(str(name))
            if norm and norm not in lookup:
                lookup[norm] = ntee
    log.info("BMF NTEE religion lookup: %d normalized names", len(lookup))
    return lookup


def run():
    lookup = build_ntee_lookup()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT name_norm, display_name FROM recipients "
        "WHERE (tags = '[]' OR tags IS NULL)"
    ).fetchall()
    log.info("Checking %d still-unclassified recipients against NTEE...",
             len(rows))

    chr_n = non_n = 0
    for norm, display in rows:
        ntee = lookup.get(norm) or lookup.get(normalize(display))
        if not ntee:
            continue
        code = ntee[:3].upper()
        if code in CHRISTIAN_NTEE:
            conn.execute("UPDATE recipients SET tags=?, source='ntee' "
                         "WHERE name_norm=?", (CHRISTIAN_TAG, norm))
            chr_n += 1
        elif code in NONCHRISTIAN_NTEE:
            conn.execute("UPDATE recipients SET tags=?, source='ntee_excl' "
                         "WHERE name_norm=?", (NONCHRISTIAN_TAG, norm))
            non_n += 1
    conn.commit()
    conn.close()
    log.info("NTEE classified: %d Christian, %d non-Christian", chr_n, non_n)


if __name__ == '__main__':
    run()
