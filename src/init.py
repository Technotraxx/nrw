"""NRW Gemeinden Extractor package."""
__version__ = "0.3.0"

# Hauptklassen und Funktionen exportieren
from .extract import Gemeinde, run_extraction, ScrapingError
from .llm import generate_summary, generate_summaries_batch, is_available as llm_available
from .export import to_csv, upsert_airtable, ExportError
from .config import Config

__all__ = [
    "Gemeinde",
    "run_extraction", 
    "ScrapingError",
    "generate_summary",
    "generate_summaries_batch", 
    "llm_available",
    "to_csv",
    "upsert_airtable",
    "ExportError", 
    "Config",
]
