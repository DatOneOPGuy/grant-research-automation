"""Religious-language detection on 990-PF grant purpose text.

Shared by the Phase 1 review queue and the Phase 2 evidence writer so both
judge a purpose string identically.

Two failure modes drove the design, both found while auditing:

  1. Substring matching. A SQL `LIKE '%CHRIST%'` scan matched "CHRISTOPH
     NABZDYK, MD" in a Mayo Clinic research grant -- the same family as the
     `cru` -> cruelty and Corpus Christi bugs. Every match here is
     word-boundary anchored.

  2. Organisational-mission noise. In purpose text a funder routinely
     describes its own or the grantee's *organisational* mission: "TO SUPPORT
     THE MISSIONS AND OPERATIONS OF THE UNIVERSITY" (UC Berkeley, $14.0M) is
     not a religious statement. Bare "mission"/"missions" therefore carries no
     weight on its own, and "ministry" is rejected when it names a government
     department ("Ministry of Health").
"""

from __future__ import annotations

import re

# Unambiguous religious vocabulary. Every one is word-boundary anchored.
STRONG = re.compile(
    r'\b(christian|christ|jesus|gospel|evangelism|evangelistic|evangelical|'
    r'evangelize|evangelization|discipleship|disciples?|bible|biblical|'
    r'scripture|scriptural|catholic|diocese|diocesan|archdiocese|parish|'
    r'church|chapel|clergy|divinity|seminary|chaplain|chaplaincy|missionary|'
    r'missionaries|faith-based|christ-centered|christ-centred|'
    r'kingdom of god|great commission|vacation bible school)\b', re.I)

# Religious only in context. "Ministry" is usually religious in a grant
# purpose, but not when it is a government department.
CONTEXTUAL = re.compile(r'\b(ministry|ministries|missions)\b', re.I)
GOVERNMENT_MINISTRY = re.compile(
    r'\bministry\s+of\s+(health|education|finance|justice|labou?r|interior|'
    r'agriculture|defen[cs]e|foreign|public)\b|\bministre\b', re.I)
# "missions and operations", "mission statement", "our mission" -- the funder
# describing an organisation's purpose, not a religious activity.
ORG_MISSION = re.compile(
    r'\bmissions?\s+(and|&)\s+(operations?|programs?|activities)\b|'
    r'\bmission\s+statement\b|\b(its|our|the organization\'?s)\s+missions?\b',
    re.I)

# Purposes that carry no information at all.
BOILERPLATE = re.compile(
    r'^\W*(general|charitable|charity|unrestricted|program|operating|'
    r'support|donation|contribution|scholarships?|education|educational|'
    r'grant|gift|annual|fund|none|n/?a|various|see\s+attached|'
    r'see\s+statement|misc\w*)[\s\W]*$', re.I)

# Non-Christian traditions, so a Christian signal is never asserted over them.
OTHER_FAITH = re.compile(
    r'\b(jewish|judaism|torah|talmud|synagogue|yeshiva|rabbin\w*|hebrew|'
    r'chabad|islam\w*|muslim|mosque|masjid|quran|hindu|buddhist|sikh|'
    r'baha\w*|latter[- ]day|mormon|christian science|jehovah)\b', re.I)


def is_boilerplate(purpose: str | None) -> bool:
    text = (purpose or '').strip()
    return not text or bool(BOILERPLATE.match(text))


def christian_signal(purpose: str | None) -> str | None:
    """Return the matched religious phrase, or None.

    Abstains freely: boilerplate, government ministries, organisational-mission
    phrasing and other-faith vocabulary all yield None.
    """
    text = (purpose or '').strip()
    if is_boilerplate(text) or OTHER_FAITH.search(text):
        return None
    match = STRONG.search(text)
    if match:
        return match.group(0)
    if GOVERNMENT_MINISTRY.search(text) or ORG_MISSION.search(text):
        return None
    match = CONTEXTUAL.search(text)
    return match.group(0) if match else None


def quote(purpose: str, limit: int = 220) -> str:
    """The verbatim purpose text, collapsed to one line for the audit trail."""
    text = re.sub(r'\s+', ' ', (purpose or '').strip())
    return text if len(text) <= limit else text[:limit].rstrip() + '…'
