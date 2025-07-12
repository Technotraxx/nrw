"""Very thin wrapper around Anthropic Claude (or OpenAI GPT‑4o).

Keeps LLM logic in one place so you can swap providers easily.
"""
from __future__ import annotations

from typing import Any, Iterable

from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT  # type: ignore

from .config import Config

cfg = Config()
_client = Anthropic(api_key=cfg.anthropic_api_key) if cfg.anthropic_api_key else None

PROMPT_TEMPLATE = (
    """{human}\n"""
    "Du erhältst strukturierte Daten zu einer nordrhein‑westfälischen Kommune als JSON. "
    "Erstelle daraus eine prägnante, sachliche Zusammenfassung (max 80 Wörter) auf Deutsch.\n"
    "{data}\n"
    "{assistant}"""
)


def generate_summary(gemeinde_dict: dict[str, Any]) -> str | None:
    """Return LLM‑generated summary text (or None if key missing)."""
    if not _client:
        return None  # Key not configured; caller decides fallback

    prompt = PROMPT_TEMPLATE.format(
        human=HUMAN_PROMPT,
        data=str(gemeinde_dict),
        assistant=AI_PROMPT,
    )
    resp = _client.completions.create(
        model="claude-3-opus-20240229",
        max_tokens_to_sample=200,
        temperature=0.3,
        prompt=prompt,
    )
    return resp.completion.strip()
