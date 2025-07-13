"""CLI-Pipeline für Headless-Runs mit umfassender Fehlerbehandlung."""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from rich import print
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.logging import RichHandler

from .extract import run_extraction, Gemeinde, ScrapingError
from .llm import generate_summaries_batch, is_available as llm_available
from .export import to_csv, upsert_airtable
from .config import Config

# Setup rich console and logging
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)

def setup_cli_args() -> argparse.ArgumentParser:
    """Konfiguriert CLI-Argumente."""
    parser = argparse.ArgumentParser(
        description="NRW Gemeinden Extractor - Kommandozeilen-Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s --limit 10 --csv test.csv
  %(prog)s --no-llm --airtable
  %(prog)s --limit 50 --llm-workers 5 --verbose
        """
    )
    
    # Basis-Optionen
    parser.add_argument(
        "--limit", 
        type=int, 
        help="Nur N Gemeinden verarbeiten (Standard: alle)"
    )
    
    parser.add_argument(
        "--char-limit",
        type=int,
        default=10000,
        help="Maximale Zeichen für Wikipedia-Volltext (Standard: 10000)"
    )
    
    # Export-Optionen
    parser.add_argument(
        "--csv", 
        default="output.csv", 
        help="CSV-Ausgabepfad (Standard: output.csv)"
    )
    
    parser.add_argument(
        "--airtable", 
        action="store_true", 
        help="Direkt in Airtable upserten"
    )
    
    # LLM-Optionen
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="LLM-Zusammenfassungen deaktivieren"
    )
    
    parser.add_argument(
        "--llm-workers",
        type=int,
        default=3,
        help="Anzahl paralleler LLM-Worker (Standard: 3)"
    )
    
    # Weitere Optionen
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Ausführliche Ausgabe"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulation ohne echte Verarbeitung"
    )
    
    return parser

def validate_args(args: argparse.Namespace, config: Config) -> bool:
    """Validiert CLI-Argumente und Konfiguration."""
    errors = []
    
    # Validiere limit
    if args.limit is not None and args.limit < 1:
        errors.append("--limit muss größer als 0 sein")
    
    # Validiere char_limit
    if args.char_limit < 1000 or args.char_limit > 50000:
        errors.append("--char-limit sollte zwischen 1000 und 50000 liegen")
    
    # Validiere LLM-Einstellungen
    if not args.no_llm and not llm_available():
        errors.append("LLM nicht verfügbar - verwende --no-llm oder setze ANTHROPIC_API_KEY")
    
    if args.llm_workers < 1 or args.llm_workers > 10:
        errors.append("--llm-workers sollte zwischen 1 und 10 liegen")
    
    # Validiere Airtable
    if args.airtable and not config.has_airtable_config:
        errors.append("Airtable nicht konfiguriert - setze AIRTABLE_API_KEY und AIRTABLE_BASE_ID")
    
    # Validiere Output-Pfad
    try:
        output_path = Path(args.csv)
        if not output_path.parent.exists():
            errors.append(f"Ausgabeverzeichnis existiert nicht: {output_path.parent}")
    except Exception as e:
        errors.append(f"Ungültiger CSV-Pfad: {e}")
    
    if errors:
        console.print("\n[red]❌ Validierungsfehler:[/red]")
        for error in errors:
            console.print(f"  • {error}")
        return False
    
    return True

def print_configuration(args: argparse.Namespace, config: Config) -> None:
    """Zeigt aktuelle Konfiguration an."""
    console.print("\n[bold blue]📋 Konfiguration:[/bold blue]")
    console.print(f"  • Gemeinden: {'Alle' if args.limit is None else args.limit}")
    console.print(f"  • Zeichenlimit: {args.char_limit:,}")
    console.print(f"  • CSV-Ausgabe: {args.csv}")
    console.print(f"  • LLM-Zusammenfassungen: {'Nein' if args.no_llm else 'Ja'}")
    
    if not args.no_llm:
        console.print(f"  • LLM-Worker: {args.llm_workers}")
        console.print(f"  • LLM-Modell: {config.anthropic_model}")
    
    console.print(f"  • Airtable-Upload: {'Ja' if args.airtable else 'Nein'}")
    console.print(f"  • Scraping-Worker: {config.max_workers}")

def run_pipeline(args: argparse.Namespace) -> int:
    """Führt die Haupt-Pipeline aus."""
    config = Config()
    
    # Validierung
    if not validate_args(args, config):
        return 1
    
    # Konfiguration anzeigen
    print_configuration(args, config)
    
    if args.dry_run:
        console.print("\n[yellow]🧪 Dry-Run-Modus - keine echte Verarbeitung[/yellow]")
        return 0
    
    console.print("\n[green]🚀 Starte Pipeline...[/green]")
    
    try:
        # Schritt 1: Wikipedia-Extraktion
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            
            extract_task = progress.add_task("📄 Extrahiere Wikipedia-Daten...", total=None)
            
            try:
                results: List[Gemeinde] = run_extraction(
                    limit=args.limit,
                    char_limit=args.char_limit
                )
                progress.update(extract_task, completed=100, total=100)
                console.print(f"[green]✅ {len(results)} Gemeinden erfolgreich extrahiert[/green]")
                
            except ScrapingError as e:
                console.print(f"[red]❌ Scraping-Fehler: {e}[/red]")
                return 1
            except Exception as e:
                console.print(f"[red]❌ Unerwarteter Extraktionsfehler: {e}[/red]")
                logger.error("Extraction error", exc_info=True)
                return 1
            
            # Schritt 2: LLM-Zusammenfassungen (optional)
            if not args.no_llm and results:
                llm_task = progress.add_task(
                    f"🤖 Generiere LLM-Zusammenfassungen ({args.llm_workers} Worker)...", 
                    total=len(results)
                )
                
                try:
                    gemeinde_dicts = [g.to_dict() for g in results]
                    summaries = generate_summaries_batch(
                        gemeinde_dicts, 
                        max_workers=args.llm_workers
                    )
                    
                    # Zusammenfassungen zuweisen
                    successful_summaries = 0
                    for gemeinde, summary in zip(results, summaries):
                        gemeinde.beschreibung_llm = summary
                        if summary:
                            successful_summaries += 1
                        progress.update(llm_task, advance=1)
                    
                    console.print(f"[green]✅ {successful_summaries}/{len(results)} LLM-Zusammenfassungen generiert[/green]")
                    
                except Exception as e:
                    console.print(f"[yellow]⚠️ LLM-Fehler: {e}[/yellow]")
                    logger.error("LLM error", exc_info=True)
            
            # Schritt 3: Export
            export_task = progress.add_task("💾 Exportiere Daten...", total=None)
            
            try:
                # CSV Export
                csv_path = to_csv(results, Path(args.csv))
                console.print(f"[green]✅ CSV erstellt: {csv_path}[/green]")
                
                # Airtable Export (optional)
                if args.airtable:
                    upsert_airtable(results)
                    console.print("[green]✅ Airtable-Upload abgeschlossen[/green]")
                
                progress.update(export_task, completed=100, total=100)
                
            except Exception as e:
                console.print(f"[red]❌ Export-Fehler: {e}[/red]")
                logger.error("Export error", exc_info=True)
                return 1
        
        # Abschluss-Statistiken
        console.print("\n[bold green]🎉 Pipeline erfolgreich abgeschlossen![/bold green]")
        
        # Statistiken
        stats = {
            "Gemeinden": len(results),
            "Mit Einwohnerzahl": sum(1 for g in results if g.einwohner),
            "Mit LLM-Zusammenfassung": sum(1 for g in results if g.beschreibung_llm),
            "Mit Website": sum(1 for g in results if g.website),
        }
        
        console.print("\n[bold blue]📊 Statistiken:[/bold blue]")
        for key, value in stats.items():
            console.print(f"  • {key}: {value}")
        
        return 0
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Pipeline durch Benutzer unterbrochen[/yellow]")
        return 1
    except Exception as e:
        console.print(f"\n[red]❌ Unerwarteter Pipeline-Fehler: {e}[/red]")
        logger.error("Pipeline error", exc_info=True)
        return 1

def main() -> None:
    """Hauptfunktion für CLI."""
    parser = setup_cli_args()
    args = parser.parse_args()
    
    # Logging-Level setzen
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Pipeline ausführen
    exit_code = run_pipeline(args)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
