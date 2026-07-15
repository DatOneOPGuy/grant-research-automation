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


def append_church_code(conn: sqlite3.Connection, run_id: str, identity_run: str) -> tuple[int, int]:
    """BMF foundation code 10 = 170(b)(1)(A)(i) house of worship.

    The code alone is NOT a Christian signal — synagogues and mosques carry
    it too — so it only becomes classification evidence when the entity's
    name yields a tradition. Code-10 entities with name-neutral names are
    counted and returned as pending (prime GEN / recipient-990 targets).
    """
    emitted = pending = 0
    for entity_id, ein, name in conn.execute(
        """
        SELECT e.entity_id, e.bmf_ein, b.organization_name
        FROM recipient_entities e JOIN bmf.bmf_organizations b ON b.ein=e.bmf_ein
        WHERE e.run_id=? AND b.foundation_code='10'
        """,
        (identity_run,),
    ):
        label = rule_label(name)
        if label is None or label == "secular":
            pending += 1
            continue
        append_evidence(
            conn,
            run_id,
            identity_run,
            Evidence(
                entity_id,
                label,
                0.97,
                "church_code_name",
                reason="IRS foundation code 10 (house of worship) + name tradition",
                source_rule_id="bmf-foundation-code-10",
                source_record={"ein": ein, "name": name, "foundation_code": "10"},
            ),
        )
        emitted += 1
    return emitted, pending


def gen_traditions(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """Map group exemption numbers to a tradition via the parent org's name.

    Only GENs whose parent orgs (affiliation 6/8) agree on exactly one
    non-secular tradition are used; ambiguous parents are dropped.
    """
    candidates: dict[str, set[str]] = {}
    parents: dict[str, str] = {}
    for gen, name in conn.execute(
        """
        SELECT group_exemption_number, organization_name
        FROM bmf.bmf_organizations
        WHERE affiliation_code IN ('6','8')
          AND group_exemption_number NOT IN ('', '0000')
        """
    ):
        label = rule_label(name)
        if label and label != "secular":
            candidates.setdefault(gen, set()).add(label)
            parents[gen] = name
    return {
        gen: (labels.pop(), parents[gen])
        for gen, labels in candidates.items()
        if len(labels) == 1
    }


def append_group_exemption(conn: sqlite3.Connection, run_id: str, identity_run: str) -> int:
    mapping = gen_traditions(conn)
    count = 0
    for entity_id, ein, name, gen in conn.execute(
        """
        SELECT e.entity_id, e.bmf_ein, b.organization_name,
               b.group_exemption_number
        FROM recipient_entities e JOIN bmf.bmf_organizations b ON b.ein=e.bmf_ein
        WHERE e.run_id=? AND b.affiliation_code='9'
          AND b.group_exemption_number NOT IN ('', '0000')
        """,
        (identity_run,),
    ):
        if gen not in mapping:
            continue
        label, parent = mapping[gen]
        append_evidence(
            conn,
            run_id,
            identity_run,
            Evidence(
                entity_id,
                label,
                0.95,
                "group_exemption",
                reason=f"subordinate under group ruling GEN {gen} ({parent})",
                source_rule_id=f"gen-{gen}",
                source_record={"ein": ein, "name": name, "gen": gen,
                               "parent_name": parent},
            ),
        )
        count += 1
    return count


def run(db_path: Path, bmf_path: Path, identity_run: str) -> str:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=rw", uri=True)
    create_classification_schema(conn)
    attach_bmf(conn, bmf_path)
    ntee_run = create_run(conn, identity_run, "ntee", engine_name="irs-eo-bmf")
    church_run = create_run(conn, identity_run, "church_code_name", engine_name="irs-eo-bmf")
    gen_run = create_run(conn, identity_run, "group_exemption", engine_name="irs-eo-bmf")
    rule_run = create_run(conn, identity_run, "rule", engine_name="recipient-name-rules-v2")
    ntee_count = append_ntee(conn, ntee_run, identity_run)
    church_count, church_pending = append_church_code(conn, church_run, identity_run)
    gen_count = append_group_exemption(conn, gen_run, identity_run)
    rule_count = append_rules(conn, rule_run, identity_run)
    conn.commit()
    release = build_release(conn, identity_run)
    issues = conn.execute(
        "SELECT COUNT(*) FROM classification_resolution_issues WHERE release_id=?", (release,)
    ).fetchone()[0]
    conn.close()
    print(f"NTEE evidence: {ntee_count:,}; church-code evidence: {church_count:,} "
          f"(+{church_pending:,} houses of worship pending tradition); "
          f"GEN evidence: {gen_count:,}; rule evidence: {rule_count:,}; "
          f"issues: {issues:,}")
    return release


def main() -> None:
    args = parse_args()
    print(f"Published classification release: {run(args.db, args.bmf_db, args.identity_run)}")


if __name__ == "__main__":
    main()
