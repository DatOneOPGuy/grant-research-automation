"""Shared taxonomy and Ollama helpers for recipient classification.

The LLM produces a religious tradition, not a generic Christian verdict.
Only the three values in ``CHRISTIAN_TRADITIONS`` count as Christian giving.
"""

from __future__ import annotations

import json
import math
import time
from typing import Any


DEFAULT_MODEL = "qwen2.5:7b"
# The coder variant is worse at recognizing organizations such as Cru or Chabad.
MODEL_KEEP_ALIVE = "10m"

TAXONOMY = frozenset({
    "evangelical_protestant",
    "catholic",
    "orthodox_christian",
    "christian_science",
    "mormon_lds",
    "jewish",
    "muslim",
    "other_religion",
    "secular",
    "unknown",
})
CHRISTIAN_TRADITIONS = frozenset({
    "evangelical_protestant",
    "catholic",
    "orthodox_christian",
})

SYSTEM_PROMPT = """You are a strict nonprofit religious-tradition labeling API.
Return only a minified JSON object matching this schema exactly:
{"classification":"evangelical_protestant"|"catholic"|"orthodox_christian"|"christian_science"|"mormon_lds"|"jewish"|"muslim"|"other_religion"|"secular"|"unknown","confidence":float,"reason":"string"}
The reason must be 8 words or fewer - just the key signal, e.g. "Baptist church", "secular hospital", "bare person name".

Apply these steps IN ORDER and stop at the first match. The vocabulary lists are illustrative, NOT exhaustive: at every step also use your general knowledge of well-known organizations, religious orders, movements, and Hebrew or Islamic terms. Recognizing a real signal from knowledge is required; inventing a signal where none exists is forbidden.

STEP 1 - Jewish: Yeshiva, Chabad, Hebrew, synagogue, Jewish Federation, Hillel, Kollel, JCC, Hadassah, B'nai, Menorah, Holocaust centers -> jewish. A congregation or temple with a Hebrew name is a synagogue -> jewish, NEVER a Christian label: "Congregation Beth-El" -> jewish, "Temple Israel" -> jewish, "Minneapolis Kollel" -> jewish, "NC Hillel" -> jewish. Exception: Messianic organizations (Jews for Jesus, Chosen People Ministries) -> evangelical_protestant.

STEP 2 - Muslim: Islamic, Muslim, mosque, masjid in the name -> muslim.

STEP 3 - Other specific traditions: christian_science ONLY on explicit signals ("Church of Christ, Scientist", "First Church of Christ Scientist", "Christian Science", "Principia"); a bare "Christ Church [placename]" -> evangelical_protestant, never christian_science. Latter-day Saints, Brigham Young, Deseret -> mormon_lds. Buddhist/Hindu temples and monasteries -> other_religion.

STEP 4 - Orthodox: Orthodox churches and ministries (Greek, Russian, Coptic, Malankara, Antiochian), and Greek saint names like Nektarios -> orthodox_christian.

STEP 5 - Protestant denomination word present? Baptist, Methodist, Presbyterian, Lutheran, Episcopal, Wesleyan, Pentecostal, or evangelical ministry names (Bible, gospel, Cru, Wycliffe, World Vision) -> evangelical_protestant. This wins even with a saint name: "St. Peter's Evangelical Lutheran Church" -> evangelical_protestant, "St. John Missionary Baptist Church" -> evangelical_protestant. GUARD: a name containing Kollel, Hillel, or any other Hebrew/Jewish term belongs to STEP 1 -> jewish and is NEVER evangelical_protestant, even when no other signal is present. evangelical_protestant is never a bucket for generic or unfamiliar religious-sounding words.

STEP 6 - Catholic. Two triggers:
(a) Catholic vocabulary: Diocese, Parish, Catholic Charities, "Our Lady", "Holy Cross", "Sacred Heart", "Immaculate", "Blessed", "Offertory", "Mount Carmel", "Cristo Rey", "Don Bosco", convents, and religious orders known to you (Jesuit, Franciscan, Capuchin, Carmelite, Dominican, Passionist, Vincentian, Salesian, Augustinian, Friars, Christian Brothers, Little Sisters of the Poor, "Order of Saint...", "Society of St..."). Catholic universities are catholic: Notre Dame, Georgetown, Fordham, Villanova, Duquesne, Gonzaga, Marquette, Boston College, St Louis University, DePaul, Loyola. A Catholic order word wins over the word Mission/Missionary: "Franciscan Mission Outreach" -> catholic, "Capuchins Soup Kitchen" -> catholic, "Missionary Sisters of the Sacred Heart" -> catholic.
(b) THE SAINT RULE: "Saint", "St.", "St", or all-caps "ST" before a personal name means Saint ("ST JOSEPH", "ST VITO", "ST FRANCIS", "ST SEBASTIAN"). IF the name contains a saint prefix AND no Protestant denomination word appeared in STEP 5, THEN the answer is catholic - this is the default for saint names, whatever the organization type: schools, academies, sports projects, shelters, pantries, food banks, endowment funds, youth programs, PTAs, communities, universities. "ST PATRICK ACADEMY" -> catholic. "ST FRANCIS SHELTER" -> catholic. "ST SEBASTIAN SPORTS PROJECT" -> catholic. "ST GEORGE ENDOWMENT FUND" -> catholic. "UNIVERSITY OF SAINT JOSEPH" -> catholic. "ST JOSEPH HOSPITAL" -> catholic. A saint name with no denomination is NEVER evangelical_protestant and NEVER unknown.
Exceptions to the saint rule (require a positive signal, not mere absence of mission): "ST"/"St" abbreviating State or a place name ("Oregon St Univ" -> secular state university; "St Louis Children's Hospital", "St Joseph County Parks", "Go St Louis Marathon" -> secular place references); an explicitly secular research hospital ("St. Jude Children's Research Hospital" -> secular).

STEP 7 - Secular: ANY organization of ANY type whose name contains no religious words is secular - universities, colleges, hospitals, health systems, foundations, museums, conservancies, land trusts, advocacy groups, civic and community organizations, sports clubs: "Beacon College Prep" -> secular, "Planned Parenthood" -> secular, "Ojai Valley Land Conservancy" -> secular, "Foundation for University Hospital NJ" -> secular. "FBO" means "for the benefit of" a named person or fund - never faith-based organization, never a religious signal: "Elizabethtown College FBO Aidan Chapple" -> secular. Classify from the name alone; missing purpose text is never a reason to answer unknown.

STEP 8 - unknown: a last resort for truly opaque names only - a bare person's name alone, an unexplained acronym, or an unreadable fragment. A recognizable institution is NEVER unknown: a university, college, hospital, or school paired with a person's name ("University of Connecticut ITF [person]", "Western New England University on behalf of [person]", "Trustees of Columbia University") is still that institution -> secular.

ABSOLUTE RULE: NEVER use evangelical_protestant, catholic, or any Christian label as a fallback when religious signals are absent. Never guess that an ambiguous name is Christian.
"""


def prompt_for(row: dict[str, Any]) -> str:
    """Build the model context while preserving empty source fields honestly."""
    name = text(row.get("display_name"))
    city = text(row.get("recipient_city")) or "not available"
    state = text(row.get("recipient_state")) or "not available"
    purpose = text(row.get("sample_purpose_text")) or "not available"
    return f"Name: {name}, Location: {city}, {state}, Purpose Context: {purpose}"


def text(value: Any) -> str:
    """Normalize nullable SQLite values for a local LLM prompt."""
    return "" if value is None else str(value).strip()


def classify_row(model: str, row: dict[str, Any]) -> tuple[str, float, str, float]:
    """Call Ollama once and validate its structured response before returning."""
    ollama = ollama_client()
    started = time.perf_counter()
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_for(row)},
        ],
        format="json",
        keep_alive=MODEL_KEEP_ALIVE,
    )
    classification, confidence, reason = parse_response(response)
    return classification, confidence, reason, time.perf_counter() - started


def parse_response(response: Any) -> tuple[str, float, str]:
    """Reject malformed model output so it follows normal retry handling."""
    content = response_content(response)
    payload = json.loads(content)
    classification = text(payload.get("classification"))
    confidence = float(payload["confidence"])
    reason = text(payload.get("reason"))
    if classification not in TAXONOMY:
        raise ValueError("Model returned an unsupported tradition.")
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("Model returned an invalid confidence.")
    if not reason:
        raise ValueError("Model returned an empty reason.")
    return classification, confidence, reason


def response_content(response: Any) -> str:
    """Support both current Ollama response objects and mapping responses."""
    message = getattr(response, "message", None)
    content = getattr(message, "content", None)
    if content is not None:
        return str(content)
    if isinstance(response, dict):
        return str(response.get("message", {}).get("content", ""))
    raise ValueError("Ollama returned no message content.")


def tags_for(tradition: str, confidence: float) -> str:
    """Keep the Explorer's legacy tag contract in sync with the new taxonomy."""
    score = round(confidence * 100)
    if tradition in CHRISTIAN_TRADITIONS:
        tags = [{"name": "Christian Ministry", "confidence": score}]
    elif tradition == "jewish":
        tags = [{"name": "Jewish Ministry", "confidence": score}]
    elif tradition in {"secular", "other_religion", "muslim", "mormon_lds", "christian_science"}:
        tags = [{"name": "Non-Christian", "confidence": score}]
    else:
        tags = []
    return json.dumps(tags, separators=(",", ":"))


def infer_legacy_tradition(name: str) -> str | None:
    """Recover precise traditions for legacy rule/NTEE records where possible."""
    from src import classifier as legacy

    normalized = f" {text(name).lower()} "
    if not normalized.strip():
        return None
    if legacy.MESSIANIC.search(normalized):
        return "evangelical_protestant"
    if legacy.CHRISTIAN_SCIENCE.search(normalized):
        return "christian_science"
    if legacy.MORMON.search(normalized):
        return "mormon_lds"
    if legacy.JEWISH.search(normalized):
        return "jewish"
    if legacy.MUSLIM.search(normalized):
        return "muslim"
    if legacy.OTHER_RELIGION.search(normalized) or legacy.JW.search(normalized):
        return "other_religion"
    # "Big Brothers Big Sisters" is secular; must not hit Catholic 'sisters of'.
    if legacy.BBBS.search(normalized):
        return "secular"
    # An explicit Protestant denomination beats saint/Catholic vocabulary
    # ("St. Peter's Evangelical Lutheran", "Episcopal Diocese of...").
    if legacy.PROT_DENOMINATION.search(normalized):
        return "evangelical_protestant"
    # Orthodox markers beat the Catholic saint/monastery vocabulary.
    if legacy.ORTHODOX.search(normalized):
        return "orthodox_christian"
    if legacy.CATHOLIC.search(normalized):
        return "catholic"
    # Saint prefix -> catholic, unless the "St" is a street/state/place name
    # or a medical/research org with no other Christian signal (St. Jude rule).
    if legacy.SAINT.search(normalized) and not legacy.SAINT_PLACE.search(normalized):
        if legacy.MEDICAL_OVERRIDE.search(normalized) and not legacy.PROTESTANT.search(normalized):
            return "secular"
        return "catholic"
    if legacy.PROTESTANT.search(normalized):
        return "evangelical_protestant"
    if legacy.SECULAR.search(normalized) or legacy.BIG_SECULAR.search(normalized):
        # An explicit religious word blocks the secular institution override
        # ("Heritage Christian University", "Revive College Church").
        if legacy.RELIGIOUS_WORD.search(normalized):
            return "evangelical_protestant"
        return "secular"
    return None


def unload_model(model: str) -> None:
    """Release model layers from Apple Unified Memory after a run."""
    try:
        ollama_client().chat(model=model, keep_alive=0)
    except Exception:
        pass


def ensure_model_available(model: str) -> None:
    """Fail before work begins if the selected local model is unavailable."""
    models = ollama_client().list()
    entries = models.get("models", []) if isinstance(models, dict) else getattr(models, "models", [])
    available = {
        text(item.get("model") if isinstance(item, dict) else getattr(item, "model", None))
        for item in entries
    }
    if model not in available:
        raise RuntimeError(
            f"Local Ollama model '{model}' is unavailable. Pull it or pass --model."
        )


def ollama_client() -> Any:
    """Import Ollama only when inference runs; migrations need no model package."""
    try:
        import ollama
    except ImportError as error:
        raise RuntimeError("Install local inference dependencies: pip install -r requirements.txt") from error
    return ollama
