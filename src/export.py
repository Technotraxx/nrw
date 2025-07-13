"""CSV- und Airtable-Export mit robuster Fehlerbehandlung."""
from __future__ import annotations
import csv
import logging
from pathlib import Path
from typing import List, Optional
from pyairtable import Table
from pyairtable.api.types import CreateRecordDict, UpdateRecordDict
from .config import Config
from .extract import Gemeinde

logger = logging.getLogger(__name__)
cfg = Config()

class ExportError(Exception):
    """Custom Exception für Export-bezogene Fehler."""
    pass

def to_csv(rows: List[Gemeinde], path: str | Path = "output.csv") -> Path:
    """
    Exportiert Gemeinde-Daten in CSV-Format.
    
    Args:
        rows: Liste von Gemeinde-Objekten
        path: Ausgabepfad für CSV-Datei
    
    Returns:
        Path-Objekt der erstellten CSV-Datei
        
    Raises:
        ExportError: Bei Fehlern während des CSV-Exports
    """
    if not rows:
        raise ExportError("Keine Daten zum Exportieren vorhanden")
    
    path = Path(path)
    
    try:
        # Stelle sicher, dass das Verzeichnis existiert
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Schreibe CSV mit robuster Fehlerbehandlung
        with path.open("w", newline="", encoding="utf-8") as f:
            fieldnames = rows[0].to_dict().keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for i, gemeinde in enumerate(rows):
                try:
                    row_data = gemeinde.to_dict()
                    # Bereinige None-Werte für bessere CSV-Kompatibilität
                    cleaned_data = {k: (v if v is not None else "") for k, v in row_data.items()}
                    writer.writerow(cleaned_data)
                except Exception as e:
                    logger.warning(f"Fehler beim Schreiben der Zeile {i} ({gemeinde.name}): {e}")
                    # Schreibe zumindest die Basis-Informationen
                    writer.writerow({"name": gemeinde.name, "url": gemeinde.url})
        
        logger.info(f"CSV erfolgreich erstellt: {path} ({len(rows)} Gemeinden)")
        return path
        
    except PermissionError:
        raise ExportError(f"Keine Berechtigung zum Schreiben in {path}")
    except OSError as e:
        raise ExportError(f"Dateisystem-Fehler beim CSV-Export: {e}")
    except Exception as e:
        raise ExportError(f"Unerwarteter Fehler beim CSV-Export: {e}")

def _prepare_airtable_record(gemeinde: Gemeinde) -> dict:
    """
    Bereitet Gemeinde-Daten für Airtable vor.
    
    Args:
        gemeinde: Gemeinde-Objekt
        
    Returns:
        Dictionary mit Airtable-kompatiblen Daten
    """
    data = gemeinde.to_dict()
    
    # Bereinige und konvertiere Daten für Airtable
    airtable_data = {}
    
    for key, value in data.items():
        if value is not None:
            # Konvertiere zu String wenn nötig (Airtable akzeptiert verschiedene Typen)
            if isinstance(value, (int, float)):
                airtable_data[key] = value
            else:
                # Begrenze String-Länge für Airtable (max 100,000 Zeichen pro Feld)
                str_value = str(value)
                if len(str_value) > 50000:  # Konservatives Limit
                    str_value = str_value[:50000] + "..."
                airtable_data[key] = str_value
    
    return airtable_data

def upsert_airtable(rows: List[Gemeinde], batch_size: int = 10) -> None:
    """
    Lädt Gemeinde-Daten in Airtable hoch (Upsert-Operation).
    
    Args:
        rows: Liste von Gemeinde-Objekten
        batch_size: Anzahl Records pro Batch (Airtable-Limit beachten)
        
    Raises:
        ExportError: Bei Fehlern während des Airtable-Uploads
    """
    if not cfg.has_airtable_config:
        raise ExportError(
            "Airtable nicht konfiguriert. Setze AIRTABLE_API_KEY und AIRTABLE_BASE_ID."
        )
    
    if not rows:
        logger.warning("Keine Daten für Airtable-Upload vorhanden")
        return
    
    try:
        table = Table(cfg.airtable_key, cfg.airtable_base_id, cfg.airtable_table_name)
        logger.info(f"Lade {len(rows)} Gemeinden in Airtable hoch...")
        
        successful_uploads = 0
        failed_uploads = 0
        
        # Verarbeite in Batches für bessere Performance und Stabilität
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            batch_records = []
            
            for gemeinde in batch:
                try:
                    record_data = _prepare_airtable_record(gemeinde)
                    batch_records.append(record_data)
                except Exception as e:
                    logger.warning(f"Fehler beim Vorbereiten von {gemeinde.name}: {e}")
                    failed_uploads += 1
            
            # Batch-Upload zu Airtable
            if batch_records:
                try:
                    # Verwende batch_upsert für bessere Performance
                    results = table.batch_upsert(
                        batch_records,
                        key_fields=["name"],  # Eindeutiger Schlüssel
                        typecast=True  # Automatische Typkonvertierung
                    )
                    successful_uploads += len(results.get("records", []))
                    logger.debug(f"Batch {i//batch_size + 1} erfolgreich hochgeladen")
                    
                except Exception as e:
                    logger.error(f"Fehler beim Batch-Upload {i//batch_size + 1}: {e}")
                    failed_uploads += len(batch_records)
        
        logger.info(
            f"Airtable-Upload abgeschlossen: "
            f"{successful_uploads} erfolgreich, {failed_uploads} fehlgeschlagen"
        )
        
        if failed_uploads > 0:
            logger.warning(f"{failed_uploads} Gemeinden konnten nicht hochgeladen werden")
            
    except Exception as e:
        raise ExportError(f"Airtable-Upload fehlgeschlagen: {e}")

def export_summary_stats(rows: List[Gemeinde], path: str | Path = "summary_stats.json") -> Path:
    """
    Erstellt eine JSON-Datei mit zusammenfassenden Statistiken.
    
    Args:
        rows: Liste von Gemeinde-Objekten
        path: Ausgabepfad für JSON-Datei
        
    Returns:
        Path-Objekt der erstellten JSON-Datei
    """
    import json
    from datetime import datetime
    
    if not rows:
        raise ExportError("Keine Daten für Statistik-Export vorhanden")
    
    path = Path(path)
    
    try:
        # Berechne Statistiken
        stats = {
            "export_timestamp": datetime.now().isoformat(),
            "total_municipalities": len(rows),
            "with_population": sum(1 for g in rows if g.einwohner),
            "with_area": sum(1 for g in rows if g.flaeche_km2),
            "with_llm_summary": sum(1 for g in rows if g.beschreibung_llm),
            "with_website": sum(1 for g in rows if g.website),
            "with_coordinates": sum(1 for g in rows if g.koordinaten),
            "population_stats": {
                "total": sum(g.einwohner for g in rows if g.einwohner),
                "average": sum(g.einwohner for g in rows if g.einwohner) / max(1, sum(1 for g in rows if g.einwohner)),
                "max": max((g.einwohner for g in rows if g.einwohner), default=0),
                "min": min((g.einwohner for g in rows if g.einwohner), default=0),
            },
            "area_stats": {
                "total_km2": sum(g.flaeche_km2 for g in rows if g.flaeche_km2),
                "average_km2": sum(g.flaeche_km2 for g in rows if g.flaeche_km2) / max(1, sum(1 for g in rows if g.flaeche_km2)),
            },
            "regierungsbezirke": list(set(g.regierungsbezirk for g in rows if g.regierungsbezirk)),
            "landkreise_count": len(set(g.landkreis for g in rows if g.landkreis)),
        }
        
        # Schreibe JSON
        with path.open("w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Statistik-Export erstellt: {path}")
        return path
        
    except Exception as e:
        raise ExportError(f"Fehler beim Statistik-Export: {e}")
