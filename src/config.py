"""Lädt Umgebungsvariablen in ein unveränderliches Config-Objekt mit Validierung."""
from __future__ import annotations
import os
import logging
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Lade .env Datei
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class Config:
    """Konfigurationsklasse mit Validierung und besseren Defaults."""
    
    # Scraper Einstellungen
    user_agent: str = os.getenv("USER_AGENT", "NRW-Gemeinden-Extractor/0.2 (contact: info@example.com)")
    max_workers: int = int(os.getenv("MAX_WORKERS", "5"))  # Reduziert für Stabilität
    
    # Anthropic API Einstellungen
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")  # ✅ Konsistent mit .env.example
    anthropic_max_tokens: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "1200"))
    
    # Airtable Einstellungen
    airtable_key: Optional[str] = os.getenv("AIRTABLE_API_KEY")
    airtable_base_id: Optional[str] = os.getenv("AIRTABLE_BASE_ID")
    airtable_table_name: str = os.getenv("AIRTABLE_TABLE_NAME", "NRW_Gemeinden")
    
    def __post_init__(self):
        """Validiert Konfigurationswerte nach Initialisierung."""
        # Validiere max_workers
        if self.max_workers < 1 or self.max_workers > 20:
            logger.warning(f"max_workers={self.max_workers} außerhalb empfohlenem Bereich (1-20)")
        
        # Validiere max_tokens
        if self.anthropic_max_tokens < 100 or self.anthropic_max_tokens > 4000:
            logger.warning(f"anthropic_max_tokens={self.anthropic_max_tokens} außerhalb empfohlenem Bereich (100-4000)")
        
        # Warne bei fehlenden API Keys
        if not self.anthropic_api_key:
            logger.info("ANTHROPIC_API_KEY nicht gesetzt - LLM-Funktionen deaktiviert")
        
        if not (self.airtable_key and self.airtable_base_id):
            logger.info("Airtable-Credentials nicht vollständig - Airtable-Export deaktiviert")
    
    @property
    def has_anthropic_key(self) -> bool:
        """Prüft ob Anthropic API Key verfügbar ist."""
        return bool(self.anthropic_api_key)
    
    @property
    def has_airtable_config(self) -> bool:
        """Prüft ob Airtable vollständig konfiguriert ist."""
        return bool(self.airtable_key and self.airtable_base_id)
    
    def to_dict(self) -> dict:
        """Konvertiert Config zu Dictionary (ohne sensible Daten)."""
        return {
            "user_agent": self.user_agent,
            "max_workers": self.max_workers,
            "anthropic_model": self.anthropic_model,
            "anthropic_max_tokens": self.anthropic_max_tokens,
            "airtable_table_name": self.airtable_table_name,
            "has_anthropic_key": self.has_anthropic_key,
            "has_airtable_config": self.has_airtable_config,
        }
