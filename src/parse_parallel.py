"""Parse all raw 990-PF XMLs into SQLite using all cores.

Workers run parse_xml_file(); the main process does the SQLite inserts.
Safe to re-run: inserts are idempotent per (EIN, tax year).
"""

import logging
import sqlite3
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from src.config import DB_PATH, RAW_DIR
from src.parser import create_tables, insert_parsed_data, parse_xml_file

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

CHUNK = 2000


def run():
    files = [str(p) for p in Path(RAW_DIR).glob('*.xml')]
    log.info("Parsing %d XML files in parallel...", len(files))

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    create_tables(conn)

    parsed = errors = 0
    with ProcessPoolExecutor() as ex:
        for i in range(0, len(files), CHUNK):
            chunk = files[i:i + CHUNK]
            futures = [ex.submit(parse_xml_file, f) for f in chunk]
            for fut in as_completed(futures):
                try:
                    data = fut.result()
                except Exception:
                    errors += 1
                    continue
                if data:
                    insert_parsed_data(conn, data)
                    parsed += 1
                else:
                    errors += 1
            conn.commit()
            if (i // CHUNK) % 10 == 0:
                log.info("  %d / %d parsed", min(i + CHUNK, len(files)),
                         len(files))

    counts = conn.execute(
        "SELECT (SELECT COUNT(*) FROM foundations), "
        "(SELECT COUNT(*) FROM grants)"
    ).fetchone()
    log.info("Done: %d parsed, %d errors. DB: %d foundation rows, "
             "%d grants.", parsed, errors, counts[0], counts[1])
    conn.close()


if __name__ == '__main__':
    run()
