"""Anthropic-Client-Wrapper mit robuster Fehlerbehandlung und Retry-Logik."""

from __future__ import annotations
import json
import logging
import time
from typing import Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from anthropic import Anthropic, APIError, RateLimitError
from .config import Config

logger = logging.getLogger(__name__)
cfg = Config()

# Initialisiere Client nur wenn API Key verfügbar
_client: Optional[Anthropic] = None
if cfg.has_anthropic_key:
    try:
        _client = Anthropic(api_key=cfg.anthropic_api_key)
        logger.info(f"Anthropic client initialized with model: {cfg.anthropic_model}")
    except Exception as e:
        logger.error(f"Failed to initialize Anthropic client: {e}")

PROMPT_TEMPLATE = """Du erhältst strukturierte JSON-Daten **inklusive gekürztem Wikipedia-Volltext** zu einer nordrhein-westfälischen Kommune.

Erstelle eine prägnante Zusammenfassung auf Deutsch mit folgenden Anforderungen:
- Maximal 120 Wörter
- Erwähne die wichtigsten Fakten (Einwohnerzahl, Lage, Besonderheiten)
- Verwende einen sachlichen, informativen Ton
- Beginne mit dem Namen der Kommune

Daten:
{data}

Zusammenfassung:"""

class LLMError(Exception):
    """Custom Exception für LLM-bezogene Fehler."""
    pass

def _safe_json_format(data: dict[str, Any]) -> str:
    """Formatiert Dictionary sicher für JSON-Output."""
    try:
        # Filtere None-Werte und sehr lange Texte für bessere API-Performance
        filtered_data = {}
        for key, value in data.items():
            if value is not None:
                if key == "full_text" and isinstance(value, str) and len(value) > 5000:
                    # Kürze sehr lange Texte
                    filtered_data[key] = value[:5000] + "..."
                else:
                    filtered_data[key] = value
        
        return json.dumps(filtered_data, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Error formatting data as JSON: {e}")
        return str(data)

def generate_summary(gemeinde_dict: dict[str, Any], max_retries: int = 3) -> Optional[str]:
    """
    Generiert eine LLM-Zusammenfassung für eine Gemeinde.
    
    Args:
        gemeinde_dict: Dictionary mit Gemeinde-Daten
        max_retries: Maximale Anzahl Wiederholungsversuche bei Fehlern
    
    Returns:
        Zusammenfassung als String oder None bei Fehlern
    """
    if _client is None:
        logger.debug("Anthropic client not available - skipping LLM summary")
        return None
    
    if not gemeinde_dict.get("name"):
        logger.warning("No municipality name provided - skipping summary")
        return None
    
    municipality_name = gemeinde_dict["name"]
    
    for attempt in range(max_retries):
        try:
            # Bereite Prompt vor
            formatted_data = _safe_json_format(gemeinde_dict)
            prompt = PROMPT_TEMPLATE.format(data=formatted_data)
            
            # API-Aufruf
            response = _client.messages.create(
                model=cfg.anthropic_model,
                max_tokens=cfg.anthropic_max_tokens,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            
            # Validiere Response
            if not response.content:
                raise LLMError("Empty response from API")
            
            summary = response.content[0].text.strip()
            
            if not summary:
                raise LLMError("Empty summary generated")
            
            # Erfolgreiche Generierung
            logger.debug(f"Generated summary for {municipality_name} (attempt {attempt + 1})")
            return summary
            
        except RateLimitError as e:
            wait_time = 2 ** attempt  # Exponential backoff
            logger.warning(f"Rate limit hit for {municipality_name} (attempt {attempt + 1}): {e}. "
                         f"Waiting {wait_time}s...")
            time.sleep(wait_time)
            
        except APIError as e:
            logger.error(f"API error for {municipality_name} (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return None
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Unexpected error generating summary for {municipality_name}: {e}")
            if attempt == max_retries - 1:
                return None
            time.sleep(1)
    
    logger.error(f"Failed to generate summary for {municipality_name} after {max_retries} attempts")
    return None

def generate_summaries_batch(gemeinden: List[dict[str, Any]], 
                           max_workers: int = 3) -> List[Optional[str]]:
    """
    Generiert Zusammenfassungen für mehrere Gemeinden parallel.
    
    Args:
        gemeinden: Liste von Gemeinde-Dictionaries
        max_workers: Anzahl paralleler Worker (begrenzt für Rate Limits)
    
    Returns:
        Liste von Zusammenfassungen (None bei Fehlern)
    """
    if _client is None:
        logger.info("Anthropic client not available - returning empty summaries")
        return [None] * len(gemeinden)
    
    if not gemeinden:
        return []
    
    logger.info(f"Generating summaries for {len(gemeinden)} municipalities using {max_workers} workers")
    
    # Verwende ThreadPoolExecutor für parallele Verarbeitung
    summaries = [None] * len(gemeinden)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Sende alle Jobs
        future_to_index = {
            executor.submit(generate_summary, gemeinde): i 
            for i, gemeinde in enumerate(gemeinden)
        }
        
        # Sammle Ergebnisse
        completed = 0
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                result = future.result(timeout=120)  # 2 Minuten Timeout pro Summary
                summaries[index] = result
                if result:
                    completed += 1
            except Exception as e:
                logger.error(f"Error in batch processing for index {index}: {e}")
            
            # Progress logging
            if (len(summaries) - list(summaries).count(None)) % 10 == 0:
                logger.info(f"Progress: {completed}/{len(gemeinden)} summaries completed")
    
    logger.info(f"Batch processing complete: {completed}/{len(gemeinden)} successful summaries")
    return summaries

def is_available() -> bool:
    """Prüft ob der LLM-Service verfügbar ist."""
    return _client is not None

def get_model_info() -> dict[str, Any]:
    """Gibt Informationen über das verwendete Modell zurück."""
    return {
        "available": is_available(),
        "model": cfg.anthropic_model if is_available() else None,
        "max_tokens": cfg.anthropic_max_tokens,
    }
