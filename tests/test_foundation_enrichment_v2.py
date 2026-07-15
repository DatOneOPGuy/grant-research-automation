from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from src.bmf_registry import BMF_SCHEMA, REQUIRED_FILES
from src.classification_store import (
    Evidence,
    append_evidence,
    build_release,
    create_classification_schema,
    create_run,
)
from src.export_v2 import run as export_v2
from src.foundation_enrichment_v2 import run
from src.provenance_schema import create_schema
from src.recipient_identity import IDENTITY_SCHEMA
from src.release_gates import run_gates
from src.release_manifest import build_manifest


def add_filing(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO filings
          (object_id,source_path,source_sha256,ein,return_type,tax_year,
           is_amended,parser_version,parse_status,parsed_at_utc)
        VALUES ('f1','f1.xml','abc','123456789','990PF',2024,0,'test',
                'parsed','2025-01-01T00:00:00+00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO foundation_filings
          (object_id,ein,tax_year,organization_name,qualifying_distributions,
           application_format,has_application_info)
        VALUES ('f1','123456789',2024,'TEST FOUNDATION',150000,
                'Submit a written proposal',1)
        """
    )
    conn.execute(
        "INSERT INTO canonical_filings VALUES ('123456789',2024,'f1','test','fixture','2025-01-01')"
    )


def add_grants(conn: sqlite3.Connection) -> None:
    grants = [
        ("g1", "MINISTRY ONE", 50_000, "paid", "positive"),
        ("g2", "MINISTRY TWO", 30_000, "paid", "positive"),
        ("g3", "MINISTRY THREE", 20_000, "paid", "positive"),
        ("g4", "SECULAR GROUP", 10_000, "paid", "positive"),
        ("g5", "UNKNOWN GROUP", 5_000, "paid", "positive"),
        ("g6", "FUTURE MINISTRY", 1_000_000, "future_approved", "positive"),
        ("g7", "ZERO ROW", 0, "paid", "zero"),
    ]
    conn.executemany(
        """
        INSERT INTO grant_transactions
          (grant_id,object_id,ein,tax_year,schedule_type,source_xpath,row_ordinal,
           recipient_name,recipient_country,is_foreign,amount_text,signed_amount,
           amount_status,purpose)
        VALUES (?,'f1','123456789',2024,?,'.//fixture',?,?,'US',0,?,?,?,'support')
        """,
        [
            (grant_id, schedule, index, name, str(amount), amount, status)
            for index, (grant_id, name, amount, schedule, status) in enumerate(grants, 1)
        ],
    )


def add_identity(conn: sqlite3.Connection) -> str:
    run_id = "identity-test"
    conn.executescript(IDENTITY_SCHEMA)
    conn.execute(
        "INSERT INTO identity_runs VALUES (?,?,?,?)",
        (run_id, "test", "bmf-test", "2025-01-01"),
    )
    for index, grant_id in enumerate(("g1", "g2", "g3", "g4"), 1):
        mention = f"m{index}"
        entity = f"e{index}"
        name = "MINISTRY" if index < 4 else "SECULAR"
        conn.execute(
            "INSERT INTO recipient_mentions "
            "(run_id, mention_id, name_norm, display_name, city_norm, city, "
            "state, country, raw_recipient_ein, grant_count, paid_dollars, "
            "max_paid_grant, first_tax_year, last_tax_year, collision_flag) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                mention,
                name.lower(),
                name,
                "",
                "",
                "",
                "US",
                "",
                1,
                1,
                1,
                2024,
                2024,
                0,
            ),
        )
        conn.execute(
            "INSERT INTO grant_recipient_links VALUES (?,?,?)", (run_id, grant_id, mention)
        )
        conn.execute(
            "INSERT INTO recipient_entities VALUES (?,?,?,?,?)",
            (run_id, entity, None, name, "unresolved"),
        )
        conn.execute(
            "INSERT INTO recipient_entity_mentions VALUES (?,?,?)", (run_id, entity, mention)
        )
    return run_id


def add_classifications(conn: sqlite3.Connection, identity_run: str) -> str:
    create_classification_schema(conn)
    run_id = create_run(conn, identity_run, "rule")
    for entity_id in ("e1", "e2", "e3"):
        append_evidence(
            conn,
            run_id,
            identity_run,
            Evidence(entity_id, "evangelical_protestant", 0.95, "rule"),
        )
    append_evidence(conn, run_id, identity_run, Evidence("e4", "secular", 0.95, "rule"))
    conn.commit()
    return build_release(conn, identity_run)


def build_enriched_database(tmp_path: Path) -> tuple[Path, str]:
    db = tmp_path / "grants_v2.db"
    conn = sqlite3.connect(db)
    create_schema(conn)
    add_filing(conn)
    add_grants(conn)
    identity_run = add_identity(conn)
    classification_release = add_classifications(conn, identity_run)
    conn.commit()
    conn.close()
    return db, run(db, identity_run, classification_release)


def test_enrichment_uses_only_positive_canonical_paid_grants(tmp_path: Path) -> None:
    db, release = build_enriched_database(tmp_path)
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT total_paid_grant_dollars,confirmed_christian_dollars,"
        "confirmed_nonchristian_dollars,unclassified_dollars,"
        "christian_recipient_count,verdict,application_status,"
        "application_status_has_evidence,latest_qualifying_distributions "
        "FROM foundation_enrichment_v2 WHERE release_id=?",
        (release,),
    ).fetchone()
    assert row == (
        115_000,
        100_000,
        10_000,
        5_000,
        3,
        "Funds Christian organizations",
        "Accepting Applications",
        1,
        150_000,
    )
    evidence_count = conn.execute(
        "SELECT COUNT(*) FROM foundation_christian_evidence_v2 WHERE release_id=?",
        (release,),
    ).fetchone()[0]
    assert evidence_count == 3
    conn.close()


def build_bmf(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(BMF_SCHEMA)
    for filename in REQUIRED_FILES:
        conn.execute("INSERT INTO bmf_sources VALUES (?,?,?)", (filename, filename, 1))
    conn.execute(
        """
        INSERT INTO bmf_organizations
          (ein,organization_name,name_norm,city,city_norm,state,zip,ntee_code,
           foundation_code,pf_filing_req_code,tax_period,source_file,source_sha256)
        VALUES ('123456789','TEST FOUNDATION','test foundation','ATLANTA',
                'atlanta','GA','30303','T20','04','1','202412','eo1.csv','eo1.csv')
        """
    )
    conn.commit()
    conn.close()


def test_v2_export_uses_one_explicit_release_and_correct_window(tmp_path: Path) -> None:
    db, release = build_enriched_database(tmp_path)
    bmf = tmp_path / "bmf.db"
    output = tmp_path / "foundation_database_v2.csv"
    build_bmf(bmf)
    assert export_v2(db, bmf, output, release) == 1
    with output.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["ein"] == "123456789"
    assert row["data_found"] == "Yes"
    assert row["tax_year_start"] == "2023"
    assert row["tax_year_end"] == "2024"
    assert row["total_paid_grant_dollars"] == "115000"
    assert row["confirmed_christian_dollars"] == "100000"
    assert row["qualifying_distributions"] == "150000"


def release_fixture(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    db, release = build_enriched_database(tmp_path)
    bmf = tmp_path / "bmf.db"
    output = tmp_path / "foundation_database_v2.csv"
    build_bmf(bmf)
    export_v2(db, bmf, output, release)
    return db, bmf, output, release


def test_release_gates_and_manifest_reconcile_end_to_end(tmp_path: Path) -> None:
    db, bmf, output, release = release_fixture(tmp_path)
    gates = run_gates(db, bmf, release, output)
    assert all(item.passed for item in gates)
    manifest = build_manifest(db, bmf, output, release)
    assert manifest["status"] == "passed"
    assert manifest["enrichment"]["tax_year_end"] == 2024
    assert manifest["enrichment"]["positive_paid_grant_dollars"] == 115_000
    assert manifest["export"]["rows"] == 1


def test_release_gate_fails_on_planted_classification_conflict(tmp_path: Path) -> None:
    db, bmf, output, release = release_fixture(tmp_path)
    conn = sqlite3.connect(db)
    classification_release = conn.execute(
        "SELECT classification_release_id FROM enrichment_releases WHERE release_id=?",
        (release,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO classification_resolution_issues VALUES (?,?,?,?)",
        (classification_release, "planted", "test_conflict", "{}"),
    )
    conn.commit()
    conn.close()
    gates = {item.name: item for item in run_gates(db, bmf, release, output)}
    assert not gates["zero_unresolved_classification_conflicts"].passed
