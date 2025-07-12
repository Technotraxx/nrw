"""Wrapper um Anthropic Claude 3 – erzeugt Kurz­beschreibungen."""
from __future__ import annotations
from typing import Any
from anthropic import Anthropic
from .config import Config

cfg = Config()
_client = Anthropic(api_key=cfg.anthropic_api_key) if cfg.anthropic_api_key else None

PROMPT = (
    "Du erhältst JSON-Daten zu einer nordrhein-westfälischen Kommune. "
    "Schreibe eine prägnante, seriöse Zusammenfassung (max 80 Wörter) auf Deutsch. "
    "Nutze Einwohner, Fläche und eventuelle Besonderheiten.\n\n"
    "Daten:\n{data}\n\nZusammenfassung:"
)

def generate_summary(data: dict[str, Any]) -> str | None:
    if _client is None:
        return None
    msg = _client.messages.create(
        model=cfg.anthropic_model,
        max_tokens=cfg.anthropic_max_tokens,
        temperature=0.3,
        system="NRW Gemeinden Extractor MVP",
        content=PROMPT.format(data=data),
    )
    return msg.content[0].text.strip() if msg.content else None
