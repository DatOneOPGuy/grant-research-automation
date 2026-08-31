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


def _normalise(text: str) -> str:
    words = [w for w in _NON_ALNUM.sub(" ", text.lower()).split()
             if w not in PLACE_WORDS]
    return " ".join(ABBREVIATIONS.get(w, w) for w in words)


def place_key(name: str | None) -> str:
    """The one canonical spelling of a place name."""
    return _normalise(_PARENS.sub(" ", name or ""))


def place_alias(name: str | None) -> str:
    """A secondary spelling for consolidated city-county governments.

    Census writes Nashville as "Nashville-Davidson metropolitan government
    (balance)" and Louisville as "Louisville/Jefferson County metro
    government"; filings write "NASHVILLE". The part before the hyphen or
    slash is what a person would call the place.

    This used to be the first WORD of any multi-word name, which was a
    serious error: it gave every "San ..." city in California the shared key
    "san" and every "New ..." the key "new". Whichever place won that vote
    captured all of them, so a filter for Los Angeles County returned
    organisations in San Francisco. Only names that actually contain a hyphen
    or slash get an alias now, and aliases are outvoted by real names.
    """
    text = _PARENS.sub(" ", name or "")
    head = re.split(r"[-/]", text, maxsplit=1)[0]
    alias = _normalise(head)
    return alias if alias and alias != place_key(name) else ""


def place_keys(name: str | None) -> list[str]:
    """Canonical name first, then any alias.

    Ordered, not a set. county_of tries these in turn and takes the first
    that resolves, so the exact name has to be tried before the looser
    alias -- iterating a set here meant the alias sometimes won by accident.
    """
    keys = [k for k in (place_key(name), place_alias(name)) if k]
    return list(dict.fromkeys(keys))


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
