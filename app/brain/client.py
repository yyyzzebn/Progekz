"""Anthropic-Anbindung + robustes JSON-Parsing (Spec, Abschnitt 5).

call_claude() schickt einen System- und einen User-Prompt an die Messages-API
und gibt den Text zurück. parse_json() macht die Antwort defensiv zu einem Dict
(Backticks/Code-Fences und Vorwort werden gestrippt, try/except).

Der API-Key kommt ausschließlich aus der `.env` (ANTHROPIC_API_KEY).
"""

import json
import logging
import re

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: anthropic.Anthropic | None = None


class BrainParseError(ValueError):
    """Die Modell-Antwort ließ sich nicht als JSON interpretieren."""


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY fehlt. Bitte in der .env setzen "
                "(siehe .env.example)."
            )
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def call_claude(system: str, user: str, max_tokens: int = 2048) -> str:
    """Ein Messages-API-Call. Liefert den zusammengesetzten Text der Antwort.

    Der System-Prompt ist pro Modus statisch -> als cacherbarer Prefix markiert
    (Prompt Caching; greift erst ab der Mindestlänge, schadet sonst nicht).
    """
    client = _get_client()
    message = client.messages.create(
        model=settings.claude_model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in message.content if b.type == "text")


def parse_json(raw: str) -> dict:
    """Wandelt eine (potenziell verschmutzte) Modell-Antwort in ein Dict.

    Robust gegen: umschließende ```/```json-Code-Fences, Vorwort/Nachwort um das
    eigentliche JSON, fehlerhafte Ränder. Wirft BrainParseError, wenn nichts geht.
    """
    text = raw.strip()

    # Code-Fences entfernen (```json ... ``` oder ``` ... ```).
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: vom ersten { bis zum letzten } herausschneiden.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("JSON-Parsing fehlgeschlagen. Rohantwort: %r", raw[:300])
    raise BrainParseError("Modell-Antwort war kein gültiges JSON.")
