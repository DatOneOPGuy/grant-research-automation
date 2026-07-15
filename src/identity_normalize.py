"""Conservative identity normalization that preserves legally meaningful words."""

from __future__ import annotations

import hashlib
import re
import unicodedata

SPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")


def normalize_identity_name(value: str | None) -> str:
    """Normalize typography only; never strip foundation/trust/church words."""
    raw = unicodedata.normalize("NFKD", value or "")
    ascii_value = raw.encode("ascii", "ignore").decode("ascii").lower()
    ascii_value = ascii_value.replace("&", " and ")
    return SPACE_RE.sub(" ", NON_ALNUM_RE.sub(" ", ascii_value)).strip()


def normalize_place(value: str | None) -> str:
    return normalize_identity_name(value)


def mention_id(name: str, city: str, state: str, country: str) -> str:
    payload = "|".join((name, city, state.upper(), country.upper()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
