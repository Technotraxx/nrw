"""Anthropic-Client-Wrapper – erzeugt Kurzbeschreibungen per Claude 3 Sonnet."""

from __future__ import annotations

from typing import Any

from anthropic import Anthropic  # SDK ≥ 0.23
from .config import Config

cfg = Config()
_client = Anthropic(api_key=cfg.anthropic_api_key) if cfg.anthropic_api_key else None

PROMPT_TEMPLATE = (
    "Du erhältst strukturierte JSON-Daten **inklusive gekürztem Wikipedia-Volltext** "
    "zu einer nordrhein-westfälischen Kommune. "
    "Erstelle eine prägnante (≤120 Wörter) Zusammenfassung auf Deutsch.\n\n"
    "{data}\n\nZusammenfassung:"
)


def generate_summary(gemeinde_dict: dict[str, Any]) -> str | None:
    """Gibt eine Kurzbeschreibung zurück oder None, falls kein API-Key gesetzt."""
    if _client is None:
        return None

    prompt = PROMPT_TEMPLATE.format(data=gemeinde_dict)

    resp = _client.messages.create(
        model=cfg.anthropic_model,
        max_tokens=cfg.anthropic_max_tokens,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )

    return resp.content[0].text.strip() if resp.content else None