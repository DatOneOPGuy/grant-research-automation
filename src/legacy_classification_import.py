"""Import legacy non-LLM labels as explicit evidence without hiding conflicts."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from src.classification_store import (
    CLASSIFICATIONS,
    Evidence,
    append_evidence,
    build_release,
    create_classification_schema,
    create_run,
)
from src.faith_config import FAITH_TAGS
from src.matcher import normalize

FAITH_TAG_SET = set(FAITH_TAGS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants_v2.db"))
    parser.add_argument("--legacy-db", type=Path, default=Path("data/grants.db"))
    parser.add_argument("--identity-run", required=True)
    return parser.parse_args()


def normalized_confidence(value, default: float = 0.85) -> float:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number > 1:
        number /= 100
    return max(0.0, min(1.0, number))


def tag_evidence(tags_json: str) -> tuple[str, float] | None:
    try:
        tags = json.loads(tags_json or "[]")
    except json.JSONDecodeError:
        return None
    names = {str(tag.get("name") or "") for tag in tags}
    confidence = max(
        (normalized_confidence(tag.get("confidence"), 0.0) for tag in tags),
        default=0.0,
    )
    if names & FAITH_TAG_SET:
        return "christian_unspecified", confidence
    if "Jewish Ministry" in names:
        return "jewish", confidence
    if "Non-Christian" in names:
        return "nonchristian_unspecified", confidence
    return None


def legacy_rows(conn: sqlite3.Connection, identity_run_id: str):
    conn.create_function("legacy_norm", 1, normalize, deterministic=True)
    return conn.execute(
        """
        SELECT DISTINCT em.entity_id, m.display_name, lr.name_norm, lr.tags,
               lr.source, lr.faith_classification, lr.classification_method,
               lr.confidence_score, lr.classification_reason
        FROM recipient_entity_mentions em
        JOIN recipient_mentions m
          ON m.run_id=em.run_id AND m.mention_id=em.mention_id
        JOIN legacy.recipients lr ON lr.name_norm=legacy_norm(m.display_name)
        WHERE em.run_id=?
        """,
        (identity_run_id,),
    )


def source_record(row: sqlite3.Row) -> dict:
    return {
        "legacy_name_norm": row[2],
        "legacy_source": row[4],
        "legacy_classification_method": row[6],
        "matched_display_name": row[1],
        "match_method": "legacy_normalized_name",
    }


def import_faith_field(
    conn: sqlite3.Connection, run_id: str, identity_run_id: str, row: sqlite3.Row
) -> str | None:
    classification = row[5]
    method = row[6]
    if method == "llm" or classification not in CLASSIFICATIONS - {"unknown"}:
        return None
    item = Evidence(
        entity_id=row[0],
        classification=classification,
        confidence=normalized_confidence(row[7]),
        method="legacy_faith_classification",
        reason=row[8] or "",
        source_record=source_record(row),
    )
    return append_evidence(conn, run_id, identity_run_id, item)


def import_tag_field(
    conn: sqlite3.Connection, run_id: str, identity_run_id: str, row: sqlite3.Row
) -> str | None:
    if row[6] == "llm" or row[4] == "llm":
        return None
    tagged = tag_evidence(row[3])
    if not tagged:
        return None
    classification, confidence = tagged
    item = Evidence(
        entity_id=row[0],
        classification=classification,
        confidence=confidence,
        method="legacy_tag",
        reason="legacy recipient tag",
        source_record=source_record(row),
    )
    return append_evidence(conn, run_id, identity_run_id, item)


def run(db_path: Path, legacy_path: Path, identity_run_id: str) -> tuple[str, str]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "ATTACH DATABASE ? AS legacy",
        (f"file:{legacy_path.resolve()}?mode=ro&immutable=1",),
    )
    create_classification_schema(conn)
    run_id = create_run(
        conn,
        identity_run_id,
        "legacy_import",
        engine_name="legacy-rules-and-ntee",
        config={"llm_evidence_imported": False, "match_method": "legacy_normalized_name"},
    )
    seen = set()
    inserted = 0
    for row in legacy_rows(conn, identity_run_id):
        for importer in (import_faith_field, import_tag_field):
            before = conn.total_changes
            key = (row[0], importer.__name__, row[5], row[3])
            if key in seen:
                continue
            seen.add(key)
            importer(conn, run_id, identity_run_id, row)
            inserted += conn.total_changes - before
    conn.commit()
    release_id = build_release(conn, identity_run_id)
    issues = conn.execute(
        "SELECT COUNT(*) FROM classification_resolution_issues WHERE release_id=?",
        (release_id,),
    ).fetchone()[0]
    conn.close()
    print(f"Imported {inserted:,} non-LLM legacy evidence rows; {issues:,} unresolved conflicts")
    return run_id, release_id


def main() -> None:
    args = parse_args()
    run(args.db, args.legacy_db, args.identity_run)


if __name__ == "__main__":
    main()
