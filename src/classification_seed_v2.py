"""Seed immutable classification evidence from direct NTEE and name rules."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from src.bmf_registry import REQUIRED_FILES
from src.classification_store import (
    Evidence,
    append_evidence,
    build_release,
    create_classification_schema,
    create_run,
)
from src.classifier import (
    CHRISTIAN_SCIENCE,
    JEWISH,
    JW,
    MORMON,
    MUSLIM,
    OTHER_RELIGION,
    PLACEHOLDER,
    UNITARIAN,
    classify,
    tradition,
)

NTEE_LABELS = {
    "X20": "christian_unspecified",
    "X21": "evangelical_protestant",
    "X22": "catholic",
    "X24": "christian_unspecified",
    "X30": "jewish",
    "X40": "muslim",
    "X50": "other_religion",
    "X70": "other_religion",
}
TRADITION_LABELS = {
    "Evangelical/Protestant": "evangelical_protestant",
    "Catholic": "catholic",
    "Orthodox": "orthodox_christian",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants_v2.db"))
    parser.add_argument("--bmf-db", type=Path, default=Path("data/bmf_registry.db"))
    parser.add_argument("--identity-run", required=True)
    return parser.parse_args()


def attach_bmf(conn: sqlite3.Connection, path: Path) -> None:
    conn.execute("ATTACH DATABASE ? AS bmf", (f"file:{path.resolve()}?mode=ro",))
    sources = {row[0] for row in conn.execute("SELECT source_file FROM bmf.bmf_sources")}
    if sources != set(REQUIRED_FILES):
        raise RuntimeError("NTEE seeding requires all four official BMF regions.")


def nonchristian_label(name: str) -> str:
    wrapped = f" {name.lower()} "
    if CHRISTIAN_SCIENCE.search(wrapped):
        return "christian_science"
    if MORMON.search(wrapped):
        return "mormon_lds"
    if JEWISH.search(wrapped):
        return "jewish"
    if MUSLIM.search(wrapped):
        return "muslim"
    if JW.search(wrapped) or UNITARIAN.search(wrapped) or OTHER_RELIGION.search(wrapped):
        return "other_religion"
    return "secular"


def rule_label(name: str) -> str | None:
    if not name or PLACEHOLDER.match(name.strip()):
        return None
    result = classify(name)
    if result == "christian":
        return TRADITION_LABELS.get(tradition(name), "christian_unspecified")
    if result == "nonchristian":
        return nonchristian_label(name)
    return None


def append_ntee(conn: sqlite3.Connection, run_id: str, identity_run: str) -> int:
    rows = conn.execute(
        """
        SELECT e.entity_id,e.bmf_ein,b.organization_name,b.ntee_code
        FROM recipient_entities e JOIN bmf.bmf_organizations b ON b.ein=e.bmf_ein
        WHERE e.run_id=? AND COALESCE(b.ntee_code,'') != ''
        """,
        (identity_run,),
    )
    count = 0
    for entity_id, ein, name, code in rows:
        label = NTEE_LABELS.get(code[:3].upper())
        if not label:
            continue
        append_evidence(
            conn,
            run_id,
            identity_run,
            Evidence(
                entity_id,
                label,
                0.98,
                "ntee",
                reason="IRS BMF religion NTEE code",
                source_ntee_code=code,
                source_record={"ein": ein, "name": name},
            ),
        )
        count += 1
    return count


def append_rules(conn: sqlite3.Connection, run_id: str, identity_run: str) -> int:
    rows = conn.execute(
        "SELECT entity_id,canonical_name,identity_status FROM recipient_entities WHERE run_id=?",
        (identity_run,),
    )
    count = 0
    for entity_id, name, identity_status in rows:
        label = rule_label(name)
        if not label:
            continue
        append_evidence(
            conn,
            run_id,
            identity_run,
            Evidence(
                entity_id,
                label,
                0.90,
                "rule",
                reason="deterministic recipient-name rule",
                source_rule_id="recipient-name-rule-v2",
                source_record={"name": name, "identity_status": identity_status},
            ),
        )
        count += 1
    return count


def run(db_path: Path, bmf_path: Path, identity_run: str) -> str:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=rw", uri=True)
    create_classification_schema(conn)
    attach_bmf(conn, bmf_path)
    ntee_run = create_run(conn, identity_run, "ntee", engine_name="irs-eo-bmf")
    rule_run = create_run(conn, identity_run, "rule", engine_name="recipient-name-rules-v2")
    ntee_count = append_ntee(conn, ntee_run, identity_run)
    rule_count = append_rules(conn, rule_run, identity_run)
    conn.commit()
    release = build_release(conn, identity_run)
    issues = conn.execute(
        "SELECT COUNT(*) FROM classification_resolution_issues WHERE release_id=?", (release,)
    ).fetchone()[0]
    conn.close()
    print(f"NTEE evidence: {ntee_count:,}; rule evidence: {rule_count:,}; issues: {issues:,}")
    return release


def main() -> None:
    args = parse_args()
    print(f"Published classification release: {run(args.db, args.bmf_db, args.identity_run)}")


if __name__ == "__main__":
    main()
