"""Cause-area taxonomy for the non-Christian side of the ledger.

The product tells a fundraiser how much of a foundation's giving went to
Christian organisations. Everything else lands in one undifferentiated
"non-Christian" bucket worth $107B, which answers no question anybody has.
A Christian youth charity does not care that a funder is "97% non-Christian";
it cares whether that funder gives to youth work, and whether the money is
reaching causes at all.

So this splits that bucket along the axis that actually changes a prospecting
decision: what the money is *for*.

Two design choices worth stating.

**Grantmaker transfers are not a cause.** NTEE group T is philanthropy and
grantmaking -- private foundations, community foundations, fundraising
intermediaries. $24.1B of the non-Christian total, 22.5%, is a grantmaker
handing money to another grantmaker, and the largest single item is $15.85B
from Gates Foundation Trust to Gates Foundation, which is one entity funding
its own operating arm. Calling that "non-Christian giving" asserts a
destination nobody knows yet; it is the same problem donor-advised funds
already get excluded for. It gets its own category rather than being counted
as a cause.

**Other faiths stay visible.** A funder of Jewish or Muslim causes is
faith-motivated but not Christian, which is a materially different prospect
from a secular funder, so the tradition wins over the NTEE sector when both
are known. A Jewish federation is filed as Jewish, not as regranting.

Source of truth is the IRS Business Master File's NTEE code, joined by EIN.
Where that fails the fallbacks are progressively weaker and are labelled as
such, because a sector assigned by guessing at a name is not the same fact as
one the IRS assigned.
"""

from __future__ import annotations

import re

# --- the taxonomy -----------------------------------------------------------

SECTORS: dict[str, str] = {
    "regranting": "Regranting & intermediaries",
    "faith_jewish": "Jewish",
    "faith_muslim": "Muslim",
    "faith_mormon_lds": "Latter-day Saints",
    "faith_christian_science": "Christian Science",
    "faith_other": "Other faith",
    "religion_unspecified": "Religion, unspecified",
    "education": "Education",
    "health": "Health & medicine",
    "human_services": "Human services & poverty",
    "youth": "Youth & recreation",
    "arts": "Arts & culture",
    "international": "International relief & development",
    "environment": "Environment & animals",
    "civic": "Civic, justice & advocacy",
    "science": "Science & research",
    "other": "Other",
    "unknown": "Sector unknown",
}

# Display order: the categories a faith-based fundraiser is most likely to be
# a plausible fit for come first, then the rest, then the two that mean "we
# cannot tell you what this funded".
SECTOR_ORDER: list[str] = [
    "faith_jewish", "faith_muslim", "faith_mormon_lds",
    "faith_christian_science", "faith_other", "religion_unspecified",
    "human_services", "youth", "education", "health", "international",
    "civic", "arts", "environment", "science", "other",
    "regranting", "unknown",
]

# NTEE major group -> sector. The groupings follow how a fundraiser thinks
# about cause areas rather than the IRS's own top level, which splits health
# four ways and lumps all of human services under one letter.
NTEE_MAJOR: dict[str, str] = {
    "A": "arts",
    "B": "education",
    "C": "environment",
    "D": "environment",          # animal-related
    "E": "health",
    "F": "health",               # mental health & crisis intervention
    "G": "health",               # voluntary health associations
    "H": "health",               # medical research
    "I": "civic",                # crime & legal
    "J": "human_services",       # employment
    "K": "human_services",       # food, agriculture & nutrition
    "L": "human_services",       # housing & shelter
    "M": "human_services",       # public safety & disaster relief
    "N": "youth",                # recreation & sports
    "O": "youth",                # youth development
    "P": "human_services",
    "Q": "international",
    "R": "civic",                # civil rights & advocacy
    "S": "civic",                # community improvement
    "T": "regranting",
    "U": "science",
    "V": "civic",                # social science
    "W": "civic",                # public & societal benefit
    "X": "religion_unspecified",
    "Y": "other",                # mutual & membership benefit
    "Z": "other",
}

# Non-Christian traditions already established by the classification pipeline.
# These outrank the NTEE sector: see the module docstring.
TRADITION_SECTOR: dict[str, str] = {
    "jewish": "faith_jewish",
    "muslim": "faith_muslim",
    "mormon_lds": "faith_mormon_lds",
    "christian_science": "faith_christian_science",
    "other_religion": "faith_other",
}

# NTEE X codes that name a specific non-Christian faith. Without these, a
# mosque with no tradition on file would read as "religion, unspecified".
NTEE_X_FAITH: dict[str, str] = {
    "X30": "faith_jewish",
    "X40": "faith_muslim",
    "X50": "faith_other",   # Buddhism
    "X70": "faith_other",   # Hinduism
}

# --- name fallback ----------------------------------------------------------

# Last resort, and the weakest evidence here by a wide margin. Every pattern
# is anchored on word boundaries and has to be unambiguous on its own: a
# sector guessed from a name is a description, not a claim about the
# organisation, but it still gets its own method label so the UI can separate
# it from what the IRS actually said.
#
# Deliberately absent: "foundation", "trust", "fund", "society", "institute",
# "center", "association". Each spans every sector in the list.
_NAME_RULES: list[tuple[str, str]] = [
    (r"\buniversit(y|ies)\b|\bcollege\b|\bschool district\b|\bacademy\b"
     r"|\bcharter school\b|\bpublic schools\b|\bscholarship\b", "education"),
    (r"\bhospital\b|\bmedical cent(er|re)\b|\bhealth system\b|\bclinic\b"
     r"|\bcancer cent(er|re)\b|\bchildren'?s hospital\b", "health"),
    (r"\bmuseum\b|\bsymphony\b|\borchestra\b|\bthea(t|tre|ter)\b|\bballet\b"
     r"|\bopera\b|\bpublic (radio|television)\b", "arts"),
    (r"\bfood bank\b|\bhomeless\b|\bhabitat for humanity\b|\bsalvation army\b"
     r"|\bmeals on wheels\b|\bhomeless shelter\b", "human_services"),
    (r"\bconservancy\b|\bland trust\b|\baudubon\b|\bwildlife\b|\bhumane socie"
     r"|\bsierra club\b|\bnature preserve\b", "environment"),
    (r"\bymca\b|\bywca\b|\bboy scouts\b|\bgirl scouts\b|\bboys & girls club"
     r"|\bboys and girls club\b|\b4-h\b|\blittle league\b", "youth"),
    (r"\bred cross\b|\bunicef\b|\boxfam\b|\bdoctors without borders\b"
     r"|\bmedecins sans\b|\bcare international\b|\bmercy corps\b",
     "international"),
    (r"\blegal aid\b|\bcivil liberties\b|\bpublic defender\b", "civic"),
    (r"\bcommunity foundation\b|\bunited way\b|\bdonor advised\b"
     r"|\bcharitable gift fund\b", "regranting"),
]

NAME_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.I), sector) for pattern, sector in _NAME_RULES
]

# Confidence per method, mirroring how the tradition classifier grades itself.
METHOD_CONFIDENCE: dict[str, str] = {
    "tradition": "high",     # the pipeline's own religious classification
    "ntee_ein": "high",      # IRS assigned it, matched on EIN
    "ntee_name": "medium",   # IRS assigned it, matched on normalised name
    "name_rule": "low",      # we inferred it from the name
}


def sector_from_ntee(ntee_code: str | None) -> str | None:
    """Map a raw NTEE code to a sector, honouring faith-specific X codes."""
    if not ntee_code:
        return None
    code = ntee_code.strip().upper()
    if not code:
        return None
    if code[:3] in NTEE_X_FAITH:
        return NTEE_X_FAITH[code[:3]]
    return NTEE_MAJOR.get(code[0])


def sector_from_name(name: str | None) -> str | None:
    if not name:
        return None
    for pattern, sector in NAME_RULES:
        if pattern.search(name):
            return sector
    return None


def is_regranting(sector: str | None) -> bool:
    return sector == "regranting"


def label(sector: str) -> str:
    return SECTORS.get(sector, sector)


# --- NTEE major groups, verbatim -------------------------------------------
#
# The sector map above regroups these into cause areas a fundraiser thinks in.
# This is the IRS's own top level, unedited, because the nonprofit browser
# mirrors the vocabulary people already meet on ProPublica and in the BMF --
# renaming the categories there would make two sources look like they
# disagree when they do not.

NTEE_MAJOR_LABELS: dict[str, str] = {
    "A": "Arts, Culture and Humanities",
    "B": "Educational Institutions and Related Activities",
    "C": "Environmental Quality, Protection and Beautification",
    "D": "Animal-Related",
    "E": "Health — General and Rehabilitative",
    "F": "Mental Health, Crisis Intervention",
    "G": "Diseases, Disorders, Medical Disciplines",
    "H": "Medical Research",
    "I": "Crime, Legal-Related",
    "J": "Employment, Job-Related",
    "K": "Food, Agriculture and Nutrition",
    "L": "Housing, Shelter",
    "M": "Public Safety, Disaster Preparedness and Relief",
    "N": "Recreation, Sports, Leisure, Athletics",
    "O": "Youth Development",
    "P": "Human Services — Multipurpose and Other",
    "Q": "International, Foreign Affairs and National Security",
    "R": "Civil Rights, Social Action, Advocacy",
    "S": "Community Improvement, Capacity Building",
    "T": "Philanthropy, Voluntarism and Grantmaking Foundations",
    "U": "Science and Technology Research Institutes, Services",
    "V": "Social Science Research Institutes, Services",
    "W": "Public, Society Benefit — Multipurpose and Other",
    "X": "Religion-Related, Spiritual Development",
    "Y": "Mutual/Membership Benefit Organizations, Other",
    "Z": "Unknown",
}


def ntee_major(code: str | None) -> str | None:
    """The single-letter NTEE major group, or None if there is no usable code."""
    letter = (code or "").strip().upper()[:1]
    return letter if letter in NTEE_MAJOR_LABELS else None


# Revenue bands, matching the boundaries ProPublica's browser uses so a number
# seen there and a number seen here fall in the same bucket. Stored as an
# integer on each row rather than computed per query, so the filter is an
# index lookup instead of a range scan over 1.5M rows.
REVENUE_BANDS: list[tuple[int, int | None, str]] = [
    (0, 25_000, "Up to $25k"),
    (25_000, 50_000, "$25k to $50k"),
    (50_000, 100_000, "$50k to $100k"),
    (100_000, 250_000, "$100k to $250k"),
    (250_000, 500_000, "$250k to $500k"),
    (500_000, 2_000_000, "$500k to $2M"),
    (2_000_000, 5_000_000, "$2M to $5M"),
    (5_000_000, 15_000_000, "$5M to $15M"),
    (15_000_000, 50_000_000, "$15M to $50M"),
    (50_000_000, 200_000_000, "$50M to $200M"),
    (200_000_000, None, "$200M and above"),
]


def revenue_band(amount: int | float | None) -> int:
    """Index into REVENUE_BANDS. Missing or negative revenue lands in band 0."""
    value = amount or 0
    for i, (lo, hi, _) in enumerate(REVENUE_BANDS):
        if value >= lo and (hi is None or value < hi):
            return i
    return 0
