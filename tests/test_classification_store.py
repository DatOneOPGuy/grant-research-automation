from __future__ import annotations

import sqlite3

import pytest

from src.classification_store import (
    Evidence,
    append_evidence,
    build_release,
    create_classification_schema,
    create_run,
)


def database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    create_classification_schema(conn)
    return conn


def test_higher_quality_evidence_wins_without_overwriting_history() -> None:
    conn = database()
    identity_run = "identity-test"
    ntee_run = create_run(conn, identity_run, "ntee")
    llm_run = create_run(conn, identity_run, "llm", engine_name="local-test")
    ntee_id = append_evidence(
        conn,
        ntee_run,
        identity_run,
        Evidence("ein:123", "catholic", 0.95, "ntee", source_ntee_code="X22"),
    )
    append_evidence(
        conn,
        llm_run,
        identity_run,
        Evidence("ein:123", "secular", 0.99, "llm", reason="generic hospital"),
    )
    release = build_release(conn, identity_run)
    selected = conn.execute(
        "SELECT evidence_id,classification FROM classification_resolutions WHERE release_id=?",
        (release,),
    ).fetchone()
    assert tuple(selected) == (ntee_id, "catholic")
    assert conn.execute("SELECT COUNT(*) FROM classification_evidence").fetchone()[0] == 2


def test_equal_priority_conflict_stays_unresolved() -> None:
    conn = database()
    identity_run = "identity-conflict"
    run = create_run(conn, identity_run, "rule")
    append_evidence(
        conn,
        run,
        identity_run,
        Evidence("mention:abc", "catholic", 0.9, "rule", source_rule_id="saint"),
    )
    append_evidence(
        conn,
        run,
        identity_run,
        Evidence("mention:abc", "secular", 0.9, "rule", source_rule_id="hospital"),
    )
    release = build_release(conn, identity_run)
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM classification_resolutions WHERE release_id=?", (release,)
        ).fetchone()[0]
        == 0
    )
    issue = conn.execute(
        "SELECT issue_type FROM classification_resolution_issues WHERE release_id=?",
        (release,),
    ).fetchone()[0]
    assert issue == "conflicting_top_priority_evidence"


def test_evidence_rows_are_immutable() -> None:
    conn = database()
    run = create_run(conn, "identity-test", "human")
    evidence_id = append_evidence(
        conn, run, "identity-test", Evidence("ein:1", "jewish", 1.0, "human")
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute(
            "UPDATE classification_evidence SET classification='catholic' WHERE evidence_id=?",
            (evidence_id,),
        )
