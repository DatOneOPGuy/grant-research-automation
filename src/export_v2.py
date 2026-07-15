"""Stream a customer foundation export from one explicit v2 enrichment release."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

FIELDS = (
    "ein",
    "foundation_name",
    "city",
    "state",
    "ntee_code",
    "data_found",
    "latest_tax_year",
    "source_object_id",
    "revenue",
    "assets",
    "qualifying_distributions",
    "application_status",
    "website",
    "phone",
    "contact_person",
    "contact_address",
    "contact_email",
    "application_format",
    "deadlines",
    "restrictions",
    "states_given_to",
    "propublica_url",
    "tax_year_start",
    "tax_year_end",
    "total_paid_grant_dollars",
    "confirmed_christian_dollars",
    "confirmed_nonchristian_dollars",
    "unclassified_dollars",
    "classification_coverage",
    "coverage_quality",
    "verdict",
    "christian_recipient_count",
    "christian_grant_count",
    "most_recent_christian_year",
    "typical_christian_grant",
    "largest_christian_grant",
    "predominant_tradition",
    "has_recent_filing",
    "has_grant_data",
    "has_contact_info",
    "has_application_details",
    "has_website",
    "is_actively_giving",
    "is_testamentary_trust",
    "is_small_fund",
    "identity_run_id",
    "classification_release_id",
    "enrichment_release_id",
    # Stable API aliases; the canonical fields above remain authoritative.
    "distributions",
    "christian_dollars_3yr",
    "total_giving_3yr",
    "christian_preview",
    "typical_grant_size",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/grants_v2.db"))
    parser.add_argument("--bmf-db", type=Path, default=Path("data/bmf_registry.db"))
    parser.add_argument("--output", type=Path, default=Path("foundation_database_v2.csv"))
    parser.add_argument("--enrichment-release")
    return parser.parse_args()


def selected_release(conn: sqlite3.Connection, requested: str | None) -> sqlite3.Row:
    if requested:
        row = conn.execute(
            "SELECT * FROM enrichment_releases WHERE release_id=? AND status='published'",
            (requested,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM enrichment_releases WHERE status='published' "
            "ORDER BY published_at_utc DESC LIMIT 1"
        ).fetchone()
    if not row:
        raise RuntimeError("No matching published enrichment release exists.")
    return row


def states_given(conn: sqlite3.Connection, year_start: int, year_end: int) -> dict[str, str]:
    states: dict[str, set[str]] = {}
    for ein, state in conn.execute(
        "SELECT ein,recipient_state FROM paid_grants "
        "WHERE tax_year BETWEEN ? AND ? AND is_foreign=0 "
        "AND COALESCE(recipient_state,'') != ''",
        (year_start, year_end),
    ):
        states.setdefault(ein, set()).add(state)
    return {ein: "; ".join(sorted(values)) for ein, values in states.items()}


def christian_previews(conn: sqlite3.Connection, release_id: str) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    for ein, name in conn.execute(
        "SELECT ein,recipient_name FROM foundation_christian_evidence_v2 "
        "WHERE release_id=? ORDER BY ein,total_paid_dollars DESC",
        (release_id,),
    ):
        counts[ein] = counts.get(ein, 0) + 1
        if len(grouped.setdefault(ein, [])) < 2:
            grouped[ein].append(name)
    previews = {}
    for ein, names in grouped.items():
        value = ", ".join(names)
        if counts[ein] > len(names):
            value += f", +{counts[ein] - len(names)} more"
        previews[ein] = value
    return previews


def foundation_rows(conn: sqlite3.Connection, release: sqlite3.Row):
    return conn.execute(
        """
        WITH universe AS (
          SELECT ein FROM bmf.bmf_organizations
          WHERE CAST(foundation_code AS INTEGER) IN (2,3,4)
             OR CAST(pf_filing_req_code AS INTEGER)=1
          UNION
          SELECT ein FROM canonical_filings WHERE tax_year BETWEEN ? AND ?
        ), latest AS (
          SELECT * FROM (
            SELECT f.*,ROW_NUMBER() OVER (
              PARTITION BY ein ORDER BY tax_year DESC,source_object_id DESC
            ) rank
            FROM canonical_foundations f WHERE tax_year BETWEEN ? AND ?
          ) WHERE rank=1
        )
        SELECT u.ein,COALESCE(NULLIF(f.organization_name,''),b.organization_name),
          COALESCE(NULLIF(f.city,''),b.city),COALESCE(NULLIF(f.state,''),b.state),
          b.ntee_code,CASE WHEN f.ein IS NULL THEN 'No' ELSE 'Yes' END,
          f.tax_year,f.source_object_id,f.total_revenue,f.assets_eoy,
          f.qualifying_distributions,e.application_status,f.website,
          COALESCE(NULLIF(f.contact_phone,''),f.phone),f.contact_person,
          f.contact_address,f.contact_email,f.application_format,f.deadlines,f.restrictions,
          e.total_paid_grant_dollars,e.confirmed_christian_dollars,
          e.confirmed_nonchristian_dollars,e.unclassified_dollars,
          e.classification_coverage,e.coverage_quality,e.verdict,
          e.christian_recipient_count,e.christian_grant_count,
          e.most_recent_christian_year,e.typical_christian_grant,
          e.largest_christian_grant,e.predominant_tradition,e.has_recent_filing,
          e.has_grant_data,e.has_contact_info,e.has_application_details,e.has_website,
          e.is_actively_giving,e.is_testamentary_trust,e.is_small_fund
        FROM universe u
        LEFT JOIN bmf.bmf_organizations b ON b.ein=u.ein
        LEFT JOIN latest f ON f.ein=u.ein
        LEFT JOIN foundation_enrichment_v2 e ON e.ein=u.ein AND e.release_id=?
        ORDER BY u.ein
        """,
        (
            release["tax_year_start"],
            release["tax_year_end"],
            release["tax_year_start"],
            release["tax_year_end"],
            release["release_id"],
        ),
    )


def export_row(
    row: sqlite3.Row,
    release: sqlite3.Row,
    states: dict[str, str],
    previews: dict[str, str],
) -> dict:
    values = dict(zip(FIELDS[:20], row[:20], strict=True))
    values["states_given_to"] = states.get(values["ein"], "")
    values["propublica_url"] = (
        "https://projects.propublica.org/nonprofits/organizations/" + values["ein"]
    )
    values["tax_year_start"] = release["tax_year_start"]
    values["tax_year_end"] = release["tax_year_end"]
    for field, value in zip(FIELDS[24:45], row[20:], strict=True):
        values[field] = value
    values["identity_run_id"] = release["identity_run_id"]
    values["classification_release_id"] = release["classification_release_id"]
    values["enrichment_release_id"] = release["release_id"]
    values["distributions"] = values["qualifying_distributions"]
    values["christian_dollars_3yr"] = values["confirmed_christian_dollars"]
    values["total_giving_3yr"] = values["total_paid_grant_dollars"]
    values["christian_preview"] = previews.get(values["ein"], "")
    values["typical_grant_size"] = values["typical_christian_grant"]
    return values


def run(db_path: Path, bmf_path: Path, output: Path, release_id: str | None = None) -> int:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS bmf", (f"file:{bmf_path.resolve()}?mode=ro",))
    release = selected_release(conn, release_id)
    states = states_given(conn, release["tax_year_start"], release["tax_year_end"])
    previews = christian_previews(conn, release["release_id"])
    count = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in foundation_rows(conn, release):
            writer.writerow(export_row(row, release, states, previews))
            count += 1
    conn.close()
    print(f"Exported {count:,} private foundations to {output}")
    return count


def main() -> None:
    args = parse_args()
    run(args.db, args.bmf_db, args.output, args.enrichment_release)


if __name__ == "__main__":
    main()
