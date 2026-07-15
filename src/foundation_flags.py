"""Conservative foundation-level prospect quality flags."""

from __future__ import annotations

import re

TRUST_UNDER_WILL = re.compile(
    r"\b(?:t\s*/?\s*u\s*/?\s*w|u\s*/?\s*w|uwo|tuw|tua|ttee|"
    r"trust under will|testamentary|char(?:itable)? (?:rem|remainder) tr|"
    r"memorial trust)\b",
    re.I,
)


def testamentary_trust(
    name: str | None, invite_only: bool, qualifying_distributions: int | None
) -> bool:
    normalized = (name or "").strip()
    if TRUST_UNDER_WILL.search(normalized):
        return True
    small_invite_trust = (
        normalized.upper().endswith(" TRUST")
        and invite_only
        and (qualifying_distributions or 0) < 50_000
    )
    return small_invite_trust
