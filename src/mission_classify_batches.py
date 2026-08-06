"""Dump mission-text items into batch files for the classification fan-out.

Source 'gold' → the frozen gold candidates (blind: no label/stratum written).
Source 'targets' → the mission_targets table (the full run).
Each batch file is a JSON list of {id, name, mission_text}; a sibling
results/ dir receives one result file per batch, enabling resumable fan-out.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

DB = Path("data/grants_v2.db")


def gold_items() -> list[dict]:
    cands = json.loads(Path("logs/gold_candidates.json").read_text())
    return [{"id": c["entity_id"], "name": c["name"],
             "mission_text": c["mission_text"]} for c in cands]


def target_items(table: str = "mission_targets") -> list[dict]:
    conn = sqlite3.connect(f"file:{DB.resolve()}?mode=ro", uri=True)
    rows = conn.execute(
        f"SELECT entity_id, name, mission_text FROM {table} "  # noqa: S608
        "ORDER BY entity_id").fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "mission_text": r[2]} for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=("gold", "targets", "ready"),
                    required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--batch-size", type=int, default=40)
    args = ap.parse_args()
    if args.source == "gold":
        items = gold_items()
    elif args.source == "ready":
        items = target_items("mission_targets_ready")
    else:
        items = target_items()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "results").mkdir(exist_ok=True)
    n = 0
    for i in range(0, len(items), args.batch_size):
        batch = items[i:i + args.batch_size]
        (args.out_dir / f"batch_{n:04d}.json").write_text(json.dumps(batch))
        n += 1
    print(f"{len(items)} items -> {n} batches of {args.batch_size} "
          f"in {args.out_dir}")


if __name__ == "__main__":
    main()
