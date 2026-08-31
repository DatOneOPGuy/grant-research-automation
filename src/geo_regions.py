"""City-to-county matching for the geo index.

Used by src/build_geo_index.py. Regions are the mirror case and live in
the backend, since only the API needs those.
"""

from __future__ import annotations

import re

# --- city -> county ---------------------------------------------------------

# Dropped when matching a place name. These are the words Census appends to
# describe what kind of place something is; a filing writes "Dover", the file
# says "Dover city", and they are the same town.
PLACE_WORDS = {
    "city", "town", "village", "borough", "cdp", "municipality", "township",
    "plantation", "corporation", "comunidad", "zona", "urbana", "and", "ccd",
    "ucd", "county", "subdivision", "division", "unorganized", "territory",
    "metropolitan", "government", "consolidated", "balance", "urban",
}

# Abbreviations filings use and Census does not.
ABBREVIATIONS = {
    "st": "saint", "ste": "sainte", "ft": "fort", "mt": "mount",
    "n": "north", "s": "south", "e": "east", "w": "west", "pt": "port",
    "hts": "heights", "spgs": "springs", "jct": "junction",
}

_PARENS = re.compile(r"\([^)]*\)")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def place_keys(name: str | None) -> set[str]:
    """Every spelling of a place worth trying, so both sides can meet.

    Returns more than one key on purpose. "Nashville-Davidson metropolitan
    government (balance)" and "NASHVILLE" have to reach each other, and the
    only way is to also index the leading word.
    """
    text = _PARENS.sub(" ", (name or "").lower())
    words = [w for w in _NON_ALNUM.sub(" ", text).split()
             if w not in PLACE_WORDS]
    words = [ABBREVIATIONS.get(w, w) for w in words]
    if not words:
        return set()
    keys = {" ".join(words)}
    if len(words) > 1:
        keys.add(words[0])
    return keys


# Values filings use to mean "not stated". Matching these to a real place
# would be worse than leaving them unplaced.
NON_PLACES = {
    "various", "na", "n a", "none", "unknown", "see attached", "attached",
    "see schedule", "schedule", "confidential", "anonymous", "multiple",
    "see list", "various locations", "not applicable", "no",
}


def is_placeholder(city: str | None) -> bool:
    return " ".join(_NON_ALNUM.sub(" ", (city or "").lower()).split()) \
        in NON_PLACES
