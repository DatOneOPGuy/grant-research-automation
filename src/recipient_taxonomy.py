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

Classification rules:
- Christian Science (Church of Christ Scientist, Principia) is christian_science.
- Mormon/LDS (Latter-day Saints, Brigham Young, Deseret) is mormon_lds.
- Jewish organizations (Yeshiva, Chabad, Hebrew, synagogue, Jewish Federation) are jewish.
- Catholic organizations (Diocese, Jesuit, Franciscan, Catholic Charities, Notre Dame, saint-named parishes) are catholic.
- Orthodox churches and ministries are orthodox_christian.
- Evangelical/Protestant organizations (Baptist, Methodist, missions, ministries, Bible, gospel, Cru, Wycliffe, World Vision) are evangelical_protestant.
- Messianic organizations (Jews for Jesus, Chosen People Ministries) are evangelical_protestant, not jewish.
- A secular organization with a saint or religious-sounding name but no religious mission, such as St. Jude Children's Research Hospital, is secular.
- When genuinely unsure, return unknown. Never guess that an ambiguous name is Christian.
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
    if legacy.CATHOLIC.search(normalized) or legacy.SAINT.search(normalized):
        return "catholic"
    if legacy.ORTHODOX.search(normalized):
        return "orthodox_christian"
    if legacy.PROTESTANT.search(normalized):
        return "evangelical_protestant"
    if legacy.SECULAR.search(normalized) or legacy.BIG_SECULAR.search(normalized):
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
