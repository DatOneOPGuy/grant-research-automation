"""Single source of truth for the mission-text classification prompt.

Both the validation gate and the full run classify with this exact prompt, so
the gate measures the production pipeline, not a different one. Model output is
structured: one object per input with tradition, confidence (0-100), and a
reason that MUST quote the deciding phrase from the mission text.
"""

from __future__ import annotations

# Allowed labels. christian_unspecified is included deliberately: a mission can
# be unambiguously Christian ("to share the love of Jesus Christ") without
# naming a denomination, and forcing evangelical_protestant would be imputation.
# It still counts as Christian in the ledger (CHRISTIAN_LABELS).
LABELS = (
    "evangelical_protestant", "catholic", "orthodox_christian",
    "christian_unspecified", "christian_science", "mormon_lds",
    "jewish", "muslim", "other_religion", "secular", "unknown",
)
CHRISTIAN = {"evangelical_protestant", "catholic", "orthodox_christian",
             "christian_unspecified"}

PROMPT_VERSION = "mission-v1"

SYSTEM = """You classify U.S. nonprofit recipients into a religious-tradition \
taxonomy using ONLY the organization's own mission / program text from its IRS \
Form 990. You are building auditable evidence: every classification must be \
justified by a phrase the organization actually wrote.

Allowed labels (use exactly one per organization):
- evangelical_protestant — Protestant/evangelical Christian purpose: gospel, \
evangelism, discipleship, church planting, missions, "make disciples", Bible/ \
scripture-centered ministry, Protestant denominations (Baptist, Methodist, \
Lutheran, Presbyterian, Pentecostal, non-denominational Christian, etc.).
- catholic — explicitly Catholic: diocese, parish, archdiocese, Catholic \
Charities, religious orders (Jesuit, Franciscan…), Catholic sacramental/ \
educational mission.
- orthodox_christian — Eastern/Oriental Orthodox Christian.
- christian_unspecified — clearly Christian purpose (Jesus Christ, the Gospel, \
Christian ministry/worship) but no denomination stated and not clearly \
Catholic/Orthodox/Protestant.
- christian_science — Church of Christ, Scientist / Christian Science.
- mormon_lds — Latter-day Saints / Mormon.
- jewish — Jewish religious or Jewish-communal purpose: synagogue, Torah, \
Hebrew/Jewish education, Jewish federation/community.
- muslim — Islamic/Muslim religious purpose: mosque, masjid, Islamic education.
- other_religion — a clear religious purpose that is none of the above \
(Hindu, Buddhist, Sikh, Baha'i, Unitarian, interfaith, etc.).
- secular — a real charitable purpose with NO religious dimension in the text \
(healthcare, education, arts, human services, research, conservation, etc.).
- unknown — the text is uninformative/boilerplate ("to support charitable \
causes", "for the benefit of the community") with no faith AND no clear \
domain signal, OR there is not enough to decide.

CRITICAL RULES:
1. Classify from the MISSION TEXT, never from the organization's name. \
"St. Joseph Hospital" whose mission says only "provide quality healthcare" is \
secular. A name that sounds religious is NOT evidence.
2. A Christian (or any religious) label REQUIRES an explicit religious signal \
in the text — a stated faith purpose, ministry, worship, evangelism, \
scripture, sacraments, or an unmistakable denominational identity in the \
mission itself. "Values-based", "compassion", or a saint's name are NOT \
enough. When a religious purpose is not explicit, choose secular or unknown.
3. Precision over coverage. Never guess a religious label from ambiguity. \
When genuinely unsure between a faith label and secular/unknown, choose \
secular or unknown.
4. The reason MUST quote the specific words from the mission text that drove \
the decision (verbatim substring), e.g. reason: 'states "to make disciples of \
all nations"'. For secular/unknown, quote the operative purpose or note the \
text is boilerplate. A reason that only restates the verdict is invalid.
5. confidence is 0-100. Use <70 when the signal is weak or the text is thin.

Return ONLY the structured result: for each input id, one object with \
{id, tradition, confidence, reason}."""


def batch_user_prompt(items: list[dict]) -> str:
    """Render a batch of {id, name, mission_text} into the user message."""
    lines = ["Classify each organization below by its mission text.\n"]
    for it in items:
        text = (it.get("mission_text") or "").replace("\n", " ").strip()
        lines.append(f"[id: {it['id']}] (name for context only, do not "
                     f"classify from it: {it.get('name', '')})\n"
                     f"MISSION: {text}\n")
    return "\n".join(lines)
