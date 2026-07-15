"""Generate an auditable manifest for one gated Foundation Explorer release."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from src.release_gates import export_facts, release_row, run_gates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants_v2.db"))
    parser.add_argument("--bmf-db", type=Path, default=Path("data/bmf_registry.db"))
    parser.add_argument("--export", type=Path, default=Path("foundation_database_v2.csv"))
    parser.add_argument("--enrichment-release", required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def filing_source_digest(conn: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for object_id, source_hash in conn.execute(
        "SELECT object_id,source_sha256 FROM filings ORDER BY object_id"
    ):
        digest.update(f"{object_id}:{source_hash}\n".encode())
    return digest.hexdigest()


def grouped(conn: sqlite3.Connection, query: str, args: tuple = ()) -> list[dict]:
    cursor = conn.execute(query, args)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor]


def source_section(conn: sqlite3.Connection) -> dict:
    return {
        "filing_count": conn.execute("SELECT COUNT(*) FROM filings").fetchone()[0],
        "filing_source_digest": filing_source_digest(conn),
        "parser_versions": grouped(
            conn, "SELECT parser_version,COUNT(*) count FROM filings GROUP BY parser_version"
        ),
        "parse_statuses": grouped(
            conn, "SELECT parse_status,COUNT(*) count FROM filings GROUP BY parse_status"
        ),
        "return_types": grouped(
            conn, "SELECT return_type,COUNT(*) count FROM filings GROUP BY return_type"
        ),
        "bmf_sources": grouped(
            conn,
            "SELECT source_file,source_sha256,row_count FROM bmf.bmf_sources ORDER BY source_file",
        ),
    }


def filing_section(conn: sqlite3.Connection) -> dict:
    tax_years = conn.execute("SELECT MIN(tax_year),MAX(tax_year) FROM canonical_filings").fetchone()
    return {
        "canonical_filing_count": conn.execute("SELECT COUNT(*) FROM canonical_filings").fetchone()[
            0
        ],
        "canonical_foundation_count": conn.execute(
            "SELECT COUNT(DISTINCT ein) FROM canonical_filings"
        ).fetchone()[0],
        "superseded_filing_count": conn.execute(
            "SELECT COUNT(*) FROM superseded_filings"
        ).fetchone()[0],
        "tax_year_min": tax_years[0],
        "tax_year_max": tax_years[1],
        "grant_rows": grouped(
            conn,
            """
            SELECT schedule_type,amount_status,COUNT(*) row_count,
                   COALESCE(SUM(signed_amount),0) signed_dollars
            FROM canonical_grants GROUP BY schedule_type,amount_status ORDER BY 1,2
            """,
        ),
    }


def identity_section(conn: sqlite3.Connection, run_id: str) -> dict:
    return {
        "run_id": run_id,
        "entity_statuses": grouped(
            conn,
            "SELECT identity_status,COUNT(*) count FROM recipient_entities "
            "WHERE run_id=? GROUP BY identity_status",
            (run_id,),
        ),
        "collision_mentions": conn.execute(
            "SELECT COUNT(*) FROM recipient_mentions WHERE run_id=? AND collision_flag=1",
            (run_id,),
        ).fetchone()[0],
        "match_methods": grouped(
            conn,
            "SELECT match_method,COUNT(*) count FROM recipient_match_candidates "
            "WHERE run_id=? AND selected=1 GROUP BY match_method",
            (run_id,),
        ),
    }


def classification_section(conn: sqlite3.Connection, release_id: str) -> dict:
    return {
        "release_id": release_id,
        "resolutions": conn.execute(
            "SELECT COUNT(*) FROM classification_resolutions WHERE release_id=?", (release_id,)
        ).fetchone()[0],
        "unresolved_issues": conn.execute(
            "SELECT COUNT(*) FROM classification_resolution_issues WHERE release_id=?",
            (release_id,),
        ).fetchone()[0],
        "labels": grouped(
            conn,
            "SELECT classification,COUNT(*) count FROM classification_resolutions "
            "WHERE release_id=? GROUP BY classification",
            (release_id,),
        ),
        "selected_evidence_methods": grouped(
            conn,
            """
            SELECT e.evidence_method,COUNT(*) count
            FROM classification_resolutions r JOIN classification_evidence e
              ON e.evidence_id=r.evidence_id
            WHERE r.release_id=? GROUP BY e.evidence_method
            """,
            (release_id,),
        ),
    }


def enrichment_section(conn: sqlite3.Connection, release: sqlite3.Row) -> dict:
    row = conn.execute(
        """
        SELECT COUNT(*),COALESCE(SUM(latest_qualifying_distributions),0),
          COALESCE(SUM(total_paid_grant_dollars),0),
          COALESCE(SUM(confirmed_christian_dollars),0),AVG(classification_coverage)
        FROM foundation_enrichment_v2 WHERE release_id=?
        """,
        (release["release_id"],),
    ).fetchone()
    return {
        "release_id": release["release_id"],
        "policy_version": release["policy_version"],
        "tax_year_start": release["tax_year_start"],
        "tax_year_end": release["tax_year_end"],
        "foundation_count": row[0],
        "latest_qualifying_distributions": row[1],
        "positive_paid_grant_dollars": row[2],
        "confirmed_christian_dollars": row[3],
        "average_dollar_coverage": row[4],
        "verdicts": grouped(
            conn,
            "SELECT verdict,COUNT(*) count FROM foundation_enrichment_v2 "
            "WHERE release_id=? GROUP BY verdict",
            (release["release_id"],),
        ),
    }


def build_manifest(
    db_path: Path, bmf_path: Path, export_path: Path, enrichment_release: str
) -> dict:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS bmf", (f"file:{bmf_path.resolve()}?mode=ro",))
    release = release_row(conn, enrichment_release)
    gates = run_gates(db_path, bmf_path, enrichment_release, export_path)
    manifest = {
        "release_id": enrichment_release,
        "status": "passed" if all(item.passed for item in gates) else "failed",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "sources": source_section(conn),
        "filings": filing_section(conn),
        "identity": identity_section(conn, release["identity_run_id"]),
        "classification": classification_section(conn, release["classification_release_id"]),
        "enrichment": enrichment_section(conn, release),
        "export": {
            **export_facts(export_path),
            "release_ids": sorted(export_facts(export_path)["release_ids"]),
            "path": str(export_path),
            "sha256": sha256_file(export_path),
        },
        "gates": [item.as_dict() for item in gates],
    }
    conn.close()
    return manifest


def write_manifest(manifest: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    temporary.replace(output)


def main() -> None:
    args = parse_args()
    manifest = build_manifest(args.db, args.bmf_db, args.export, args.enrichment_release)
    output = args.output or Path("data/releases") / f"{args.enrichment_release}.json"
    write_manifest(manifest, output)
    print(f"Wrote {manifest['status']} release manifest: {output}")
    if manifest["status"] != "passed":
        raise SystemExit("Release failed integrity gates; do not publish it.")


if __name__ == "__main__":
    main()
