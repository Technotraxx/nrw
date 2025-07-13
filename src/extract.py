"""NRW-Gemeinden – Verbesserte Version mit robuster Fehlerbehandlung."""

from __future__ import annotations
import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import Any, List, Optional, Tuple
from urllib.parse import quote

import pandas as pd
import requests
from bs4 import BeautifulSoup
from rich.progress import track
from .config import Config

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

cfg = Config()
_session = requests.Session()
_session.headers.update({"User-Agent": cfg.user_agent})

# -------------------- Datenmodell --------------------
@dataclass
class Gemeinde:
    name: str
    url: str
    einwohner: Optional[int] = None
    einwohner_datum: Optional[str] = None
    flaeche_km2: Optional[float] = None
    hoehe_m: Optional[int] = None
    gemeindeschluessel: Optional[str] = None
    landkreis: Optional[str] = None
    regierungsbezirk: Optional[str] = None
    bundesland: Optional[str] = None
    postleitzahl: Optional[str] = None
    vorwahl: Optional[str] = None
    kfz_kennzeichen: Optional[str] = None
    koordinaten: Optional[str] = None
    koordinaten_url: Optional[str] = None
    website: Optional[str] = None
    buergermeister: Optional[str] = None
    full_text: Optional[str] = None
    beschreibung_llm: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class ScrapingError(Exception):
    """Custom exception for scraping errors."""
    pass

# -------------------- Helper Functions --------------------
def _get(url: str, max_retries: int = 3) -> str:
    """Robuste HTTP-Get-Funktion mit Retry-Logik."""
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            response = _session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            last_exception = e
            wait_time = 2 ** attempt  # Exponential backoff
            logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
    
    # Alle Versuche fehlgeschlagen
    raise ScrapingError(f"Failed to fetch {url} after {max_retries} attempts: {last_exception}")

def _lower_keys(df: pd.DataFrame) -> dict[str, str]:
    """Konvertiert DataFrame zu dict mit lowercase keys."""
    result = {}
    try:
        for _, row in df.iterrows():
            if len(row) >= 2:
                key = str(row.iloc[0]).strip().lower().rstrip(":")
                value = str(row.iloc[1]).strip()
                if key and value and value != 'nan':
                    result[key] = value
    except Exception as e:
        logger.warning(f"Error processing dataframe: {e}")
    return result

def _first(data: dict, keys: list[str]) -> Optional[str]:
    """Gibt den ersten gefundenen Wert für die gegebenen Keys zurück."""
    for key in keys:
        if key in data and data[key]:
            return data[key]
    return None

def _safe_int(value: str) -> Optional[int]:
    """Sicherer Integer-Parser."""
    try:
        # Entferne Punkte (deutsche Tausendertrennzeichen) und andere non-digits
        cleaned = re.sub(r'[^\d]', '', value)
        return int(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None

def _safe_float(value: str) -> Optional[float]:
    """Sicherer Float-Parser für deutsche Dezimalzahlen."""
    try:
        # Ersetze Komma mit Punkt und entferne andere non-numeric Zeichen außer Punkt
        cleaned = re.sub(r'[^\d,.]', '', value).replace(',', '.')
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None

# -------------------- Parsing Functions --------------------
def _parse_infobox(url: str) -> dict[str, Any]:
    """Parst die Wikipedia-Infobox mit robuster Fehlerbehandlung."""
    info = {}
    
    try:
        # Versuche mehrere Tabellen zu finden
        tables = pd.read_html(url)
        if not tables:
            logger.warning(f"No tables found in {url}")
            return info
            
        # Suche nach der richtigen Infobox-Tabelle
        infobox_data = None
        for table in tables:
            if len(table.columns) >= 2:
                infobox_data = _lower_keys(table)
                break
        
        if not infobox_data:
            logger.warning(f"No suitable infobox table found in {url}")
            return info
            
    except Exception as e:
        logger.warning(f"Error reading HTML tables from {url}: {e}")
        return info

    # Einwohner + Datum parsen
    einwohner_text = _first(infobox_data, ["einwohner", "bevölkerung"])
    if einwohner_text:
        # Einwohnerzahl extrahieren
        if match := re.search(r'([\d\.]+)', einwohner_text):
            info["einwohner"] = _safe_int(match.group(1))
        
        # Datum extrahieren
        if date_match := re.search(r'\(([^)]*)\)', einwohner_text):
            info["einwohner_datum"] = date_match.group(1).strip()

    # Fläche parsen
    flaeche_text = infobox_data.get("fläche")
    if flaeche_text:
        if match := re.search(r'([\d,\.]+)', flaeche_text):
            info["flaeche_km2"] = _safe_float(match.group(1))

    # Höhe parsen
    hoehe_text = infobox_data.get("höhe")
    if hoehe_text:
        if match := re.search(r'(\d+)', hoehe_text):
            info["hoehe_m"] = _safe_int(match.group(1))

    # Direkte Feldmappings
    field_mappings = {
        "gemeindeschlüssel": "gemeindeschluessel",
        "landkreis": "landkreis", 
        "regierungsbezirk": "regierungsbezirk",
        "bundesland": "bundesland",
        "postleitzahl": "postleitzahl",
        "vorwahl": "vorwahl",
        "kfz-kennzeichen": "kfz_kennzeichen",
    }
    
    for source_key, target_key in field_mappings.items():
        if value := infobox_data.get(source_key):
            info[target_key] = value

    # Website normalisieren
    website = _first(infobox_data, ["website", "homepage"])
    if website:
        info["website"] = website if website.startswith("http") else f"https://{website}"

    # Bürgermeister bereinigen
    buergermeister = _first(infobox_data, ["bürgermeister", "oberbürgermeister"])
    if buergermeister:
        # Entferne Klammern und extra Whitespace
        cleaned = re.sub(r'\([^)]*\)', '', buergermeister).strip()
        info["buergermeister"] = cleaned

    return info

def _parse_coordinates_and_text(url: str, char_limit: int) -> dict[str, Any]:
    """Parst Koordinaten und Volltext aus der HTML-Seite."""
    info = {}
    
    try:
        html = _get(url)
        soup = BeautifulSoup(html, "html.parser")
        
        # Koordinaten parsen
        geo_elem = soup.select_one("table.infobox span.geo")
        if geo_elem:
            info["koordinaten"] = geo_elem.text.strip()
            # Prüfe ob Parent ein Link ist
            if geo_elem.parent and geo_elem.parent.name == "a":
                href = geo_elem.parent.get("href")
                if href:
                    info["koordinaten_url"] = href
        
        # Fallback für GeoHack-Link
        if not info.get("koordinaten_url"):
            geohack_link = soup.find("a", href=re.compile(r"geohack"))
            if geohack_link:
                info["koordinaten_url"] = geohack_link["href"]

        # Volltext extrahieren
        content_div = soup.find("div", class_="mw-parser-output")
        if content_div:
            # Entferne störende Elemente
            for element in content_div.find_all(["table", "div"], 
                                               class_=re.compile(r"(infobox|navbox|metadata|dablink)")):
                element.decompose()
            
            # Extrahiere Text
            text = content_div.get_text(" ", strip=True)
            if text:
                info["full_text"] = text[:char_limit]
        
    except Exception as e:
        logger.error(f"Error parsing coordinates/text from {url}: {e}")
    
    return info

def parse_page(name: str, url: str, char_limit: int) -> dict[str, Any]:
    """Hauptfunktion zum Parsen einer Gemeinde-Seite."""
    try:
        # Infobox parsen
        info = _parse_infobox(url)
        
        # Koordinaten und Volltext hinzufügen
        additional_info = _parse_coordinates_and_text(url, char_limit)
        info.update(additional_info)
        
        return info
        
    except Exception as e:
        logger.error(f"Error parsing page {name} ({url}): {e}")
        return {}

# -------------------- Main Pipeline --------------------
LIST_URL = "https://de.wikipedia.org/wiki/Liste_der_Gemeinden_in_Nordrhein-Westfalen"

def get_gemeinden_list() -> List[Tuple[str, str]]:
    """Extrahiert die Liste aller NRW-Gemeinden von Wikipedia."""
    try:
        html = _get(LIST_URL)
        soup = BeautifulSoup(html, "html.parser")
        
        gemeinden = []
        for link in soup.select("table.wikitable tbody tr td:first-child a"):
            href = link.get("href")
            if href and href.startswith("/wiki/"):
                name = link.get("title") or href.split("/wiki/")[1].replace("_", " ")
                url = f"https://de.wikipedia.org{href}"
                gemeinden.append((name, url))
        
        logger.info(f"Found {len(gemeinden)} municipalities")
        return gemeinden
        
    except Exception as e:
        logger.error(f"Error fetching municipality list: {e}")
        raise ScrapingError(f"Failed to get municipality list: {e}")

def fetch_one(job: Tuple[str, str, int]) -> Gemeinde:
    """Verarbeitet eine einzelne Gemeinde."""
    name, url, char_limit = job
    try:
        parsed_data = parse_page(name, url, char_limit)
        return Gemeinde(name=name, url=url, **parsed_data)
    except Exception as e:
        logger.error(f"Error processing {name}: {e}")
        # Gib zumindest die Basisdaten zurück
        return Gemeinde(name=name, url=url)

def run_extraction(limit: Optional[int] = None, char_limit: int = 10000) -> List[Gemeinde]:
    """Hauptfunktion für die Extraktion aller Gemeinden."""
    try:
        # Gemeinden-Liste abrufen
        all_municipalities = get_gemeinden_list()
        municipalities_to_process = all_municipalities[:limit] if limit else all_municipalities
        
        logger.info(f"Processing {len(municipalities_to_process)} municipalities")
        
        # Jobs vorbereiten
        jobs = [(name, url, char_limit) for name, url in municipalities_to_process]
        
        # Parallel verarbeiten
        results = []
        with ThreadPoolExecutor(max_workers=cfg.max_workers) as executor:
            future_to_job = {executor.submit(fetch_one, job): job for job in jobs}
            
            for future in track(as_completed(future_to_job), 
                              total=len(jobs), 
                              description="Scraping municipalities"):
                try:
                    result = future.result(timeout=60)  # 60s timeout per task
                    results.append(result)
                except Exception as e:
                    job = future_to_job[future]
                    logger.error(f"Failed to process {job[0]}: {e}")
                    # Fallback: minimale Gemeinde-Instanz
                    results.append(Gemeinde(name=job[0], url=job[1]))
        
        logger.info(f"Successfully processed {len(results)} municipalities")
        return results
        
    except Exception as e:
        logger.error(f"Error in extraction pipeline: {e}")
        raise
