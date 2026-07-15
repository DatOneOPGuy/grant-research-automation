from __future__ import annotations

import sqlite3
from pathlib import Path

from src.bmf_registry import BMF_SCHEMA, REQUIRED_FILES
from src.identity_normalize import normalize_identity_name
from src.provenance_schema import create_schema
from src.recipient_identity import run


def build_grants_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    create_schema(conn)
    conn.execute(
        """
        INSERT INTO filings
          (object_id,source_path,source_sha256,ein,return_type,tax_year,
           is_amended,parser_version,parse_status,parsed_at_utc)
        VALUES ('fixture','fixture.xml','abc','123456789','990PF',2023,
                0,'test','parsed','2024-01-01T00:00:00+00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO canonical_filings
          (ein,tax_year,object_id,policy_version,selection_reason,selected_at_utc)
        VALUES ('123456789',2023,'fixture','test','fixture',
                '2024-01-01T00:00:00+00:00')
        """
    )
    rows = [
        ("g1", "PAID MINISTRY", "MACON", "GA", 100_000),
        ("g2", "COMMON CHURCH", "ATLANTA", "GA", 50_000),
        ("g3", "UNKNOWN GROUP", "SAVANNAH", "GA", 25_000),
    ]
    conn.executemany(
        """
        INSERT INTO grant_transactions
          (grant_id,object_id,ein,tax_year,schedule_type,source_xpath,
           row_ordinal,recipient_name,recipient_city,recipient_state,
           recipient_country,is_foreign,amount_text,signed_amount,
           amount_status,purpose)
        VALUES (?,'fixture','123456789',2023,'paid','.//paid',?, ?,?,?,'US',
                0,?,?, 'positive','support')
        """,
        [
            (grant_id, index, name, city, state, str(amount), amount)
            for index, (grant_id, name, city, state, amount) in enumerate(rows, 1)
        ],
    )
    conn.commit()
    conn.close()


def build_bmf_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(BMF_SCHEMA)
    for filename in REQUIRED_FILES:
        conn.execute("INSERT INTO bmf_sources VALUES (?,?,?)", (filename, filename, 1))
    organizations = [
        ("111111111", "PAID MINISTRY", "paid ministry", "MACON", "macon", "GA"),
        ("222222222", "COMMON CHURCH", "common church", "ATLANTA", "atlanta", "GA"),
        ("333333333", "COMMON CHURCH", "common church", "ATLANTA", "atlanta", "GA"),
    ]
    conn.executemany(
        """
        INSERT INTO bmf_organizations
          (ein,organization_name,name_norm,city,city_norm,state,zip,ntee_code,
           foundation_code,pf_filing_req_code,tax_period,source_file,source_sha256)
        VALUES (?,?,?,?,?,?,'','','','','','eo1.csv','eo1.csv')
        """,
        organizations,
    )
    conn.commit()
    conn.close()


def test_identity_normalization_preserves_legal_words() -> None:
    assert normalize_identity_name("The Grace Foundation & Trust, Inc.") == (
        "the grace foundation and trust inc"
    )


def test_identity_resolution_selects_only_unambiguous_matches(tmp_path: Path) -> None:
    grants = tmp_path / "grants.db"
    bmf = tmp_path / "bmf.db"
    build_grants_database(grants)
    build_bmf_database(bmf)
    run_id = run(grants, bmf)
    conn = sqlite3.connect(grants)
    counts = dict(
        conn.execute(
            "SELECT identity_status,COUNT(*) FROM recipient_entities "
            "WHERE run_id=? GROUP BY identity_status",
            (run_id,),
        )
    )
    assert counts == {"matched_bmf": 1, "collision": 1, "unresolved": 1}
    selected = conn.execute(
        "SELECT candidate_ein FROM recipient_match_candidates WHERE run_id=? AND selected=1",
        (run_id,),
    ).fetchall()
    assert selected == [("111111111",)]
    conn.close()
