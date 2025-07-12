"""Centralised configuration using environment variables for easy tweaking."""
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    """Holds runtime configuration pulled from the environment."""

    # Scraper
    user_agent: str = os.getenv("USER_AGENT", "NRW-Scraper/0.1")
    max_workers: int = int(os.getenv("MAX_WORKERS", "8"))

    # Anthropic
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")

    # Airtable
    airtable_key: str | None = os.getenv("AIRTABLE_API_KEY")
    airtable_base_id: str | None = os.getenv("AIRTABLE_BASE_ID")
    airtable_table_name: str = os.getenv("AIRTABLE_TABLE_NAME", "NRW_Gemeinden")
