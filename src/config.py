"""Lädt Umgebungsvariablen in ein unveränderliches Config-Objekt."""
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    # Scraper
    user_agent: str = os.getenv("USER_AGENT", "NRW-Scraper/0.2")
    max_workers: int = int(os.getenv("MAX_WORKERS", "10"))

    # Anthropic
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
    anthropic_max_tokens: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "1200"))

    # Airtable
    airtable_key: str | None = os.getenv("AIRTABLE_API_KEY")
    airtable_base_id: str | None = os.getenv("AIRTABLE_BASE_ID")
    airtable_table_name: str = os.getenv("AIRTABLE_TABLE_NAME", "NRW_Gemeinden")
