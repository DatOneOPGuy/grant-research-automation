from __future__ import annotations

import sqlite3
from pathlib import Path

from src.bmf_registry import BMF_SCHEMA, REQUIRED_FILES
from src.classification_seed_v2 import run
from src.recipient_identity import IDENTITY_SCHEMA


def build_identity_database(path: Path) -> str:
    identity_run = "identity-seed-test"
    conn = sqlite3.connect(path)
    conn.executescript(IDENTITY_SCHEMA)
    conn.execute(
        "INSERT INTO identity_runs VALUES (?,?,?,?)",
        (identity_run, "test", "bmf-digest", "2026-01-01"),
    )
    entities = [
        (identity_run, "e1", "111111111", "TRINITY HEALTH", "matched_bmf"),
        (identity_run, "e2", None, "FIRST BAPTIST CHURCH", "unresolved"),
        (identity_run, "e3", None, "VARIOUS RECIPIENTS", "unresolved"),
        (identity_run, "e4", None, "JEWISH FEDERATION", "unresolved"),
    ]
    conn.executemany("INSERT INTO recipient_entities VALUES (?,?,?,?,?)", entities)
    conn.commit()
    conn.close()
    return identity_run


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
        VALUES ('111111111','TRINITY HEALTH','trinity health','','','','',
                'X22','','','','eo1.csv','eo1.csv')
        """
    )
    conn.commit()
    conn.close()


def test_direct_ntee_and_rule_evidence_resolve_without_legacy_names(tmp_path: Path) -> None:
    db = tmp_path / "grants_v2.db"
    bmf = tmp_path / "bmf.db"
    identity_run = build_identity_database(db)
    build_bmf(bmf)
    release = run(db, bmf, identity_run)
    conn = sqlite3.connect(db)
    resolved = dict(
        conn.execute(
            "SELECT entity_id,classification FROM classification_resolutions WHERE release_id=?",
            (release,),
        )
    )
    assert resolved["e1"] == "catholic"
    assert resolved["e2"] == "evangelical_protestant"
    assert "e3" not in resolved
    assert resolved["e4"] == "jewish"
    selected_method = conn.execute(
        """
        SELECT e.evidence_method FROM classification_resolutions r
        JOIN classification_evidence e ON e.evidence_id=r.evidence_id
        WHERE r.release_id=? AND r.entity_id='e1'
        """,
        (release,),
    ).fetchone()[0]
    assert selected_method == "ntee"
    conn.close()
