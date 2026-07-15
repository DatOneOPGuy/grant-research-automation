"""Pure and query-backed values used in foundation enrichment rows."""

from __future__ import annotations

import sqlite3

from src.application_access import application_status
from src.foundation_flags import testamentary_trust

VERDICT_DOLLARS = 100_000
VERDICT_RECIPIENTS = 3


def coverage_quality(coverage: float) -> str:
    if coverage >= 0.85:
        return "High"
    if coverage >= 0.60:
        return "Moderate"
    return "Low"


def verdict(christian_dollars: int, recipient_count: int) -> str:
    if christian_dollars <= 0 or recipient_count == 0:
        return "No confirmed Christian giving"
    if christian_dollars >= VERDICT_DOLLARS and recipient_count >= VERDICT_RECIPIENTS:
        return "Funds Christian organizations"
    return "Some Christian giving"


def tradition_label(classification: str | None) -> str:
    if not classification:
        return ""
    if classification == "Mixed":
        return classification
    labels = {
        "evangelical_protestant": "Evangelical/Protestant",
        "catholic": "Catholic",
        "orthodox_christian": "Orthodox",
        "christian_unspecified": "Christian/Unspecified",
    }
    return labels.get(classification, "Christian/Unspecified")


def enrichment_row(
    release_id: str,
    profile: sqlite3.Row,
    year_end: int,
    metrics: sqlite3.Row,
    tradition: str | None,
) -> tuple:
    total, grant_count, christian, nonchristian, unclassified = metrics[:5]
    coverage = (christian + nonchristian) / total if total else 0.0
    status, status_evidence = application_status(dict(profile))
    contact_keys = ("contact_person", "contact_address", "contact_phone", "contact_email", "phone")
    detail_keys = ("application_format", "deadlines", "restrictions")
    qualifying = profile["qualifying_distributions"]
    return (
        release_id,
        profile["ein"],
        profile["tax_year"],
        profile["source_object_id"],
        qualifying,
        total,
        grant_count,
        christian,
        nonchristian,
        unclassified,
        coverage,
        coverage_quality(coverage),
        metrics[5],
        metrics[6] or 0,
        metrics[7],
        metrics[8] or 0,
        metrics[9] or 0,
        tradition_label(tradition),
        verdict(christian, metrics[5]),
        status,
        int(status_evidence),
        int(profile["tax_year"] == year_end),
        int(grant_count > 0),
        int(any(profile[key] for key in contact_keys)),
        int(any(profile[key] for key in detail_keys)),
        int(bool(profile["website"])),
        int(total > 10_000),
        int(
            testamentary_trust(
                profile["organization_name"], bool(profile["invite_only"]), qualifying
            )
        ),
        int((qualifying or 0) < 10_000),
    )
