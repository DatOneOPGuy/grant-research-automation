"""Conservative customer-facing application-access interpretation."""

from __future__ import annotations

import re

PLACEHOLDER = re.compile(r"^(?:n/?a|none|not applicable|unknown|see attached|\-+)?$", re.I)
INVITE_ONLY = re.compile(
    r"no unsolicited|not accept unsolicited|does not accept|not accepting|"
    r"by invitation|invitation only|preselected|pre-selected|predetermined|"
    r"initiated by (?:the )?(?:foundation|trust|donor)|not solicit",
    re.I,
)
CONTACT_FIRST = re.compile(
    r"upon (?:contact|request)|contacting|by (?:telephone|phone|referral)|"
    r"must (?:first )?contact|provided upon|will be provided|by referral only",
    re.I,
)


def meaningful(value: str | None) -> bool:
    return bool(value and not PLACEHOLDER.fullmatch(value.strip()))


def application_status(record: dict) -> tuple[str, bool]:
    """Return a status and whether affirmative filing evidence supports it."""
    if record.get("invite_only"):
        return "Invite Only", True
    fields = {
        name: str(record.get(name) or "").strip()
        for name in (
            "application_format",
            "deadlines",
            "restrictions",
            "contact_person",
            "contact_address",
            "contact_phone",
            "contact_email",
        )
    }
    blob = " ".join(fields.values())
    if INVITE_ONLY.search(blob):
        return "Invite Only", True
    if CONTACT_FIRST.search(blob):
        return "Contact First", True
    instructions = any(
        meaningful(fields[name]) for name in ("application_format", "deadlines", "restrictions")
    )
    if instructions:
        return "Accepting Applications", True
    contact = any(
        meaningful(fields[name])
        for name in ("contact_person", "contact_address", "contact_phone", "contact_email")
    )
    if contact:
        return "Contact First", True
    return "Unknown", False
