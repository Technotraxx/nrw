"""CLI-Pipeline für Headless-Runs ohne Streamlit."""
from __future__ import annotations
import argparse
from rich import print
from .extract import run_extraction
from .llm import generate_summary
from .export import to_csv, upsert_airtable

def main() -> None:
    ap = argparse.ArgumentParser(description="NRW Gemeinden Pipeline")
    ap.add_argument("--limit", type=int, help="Nur N Gemeinden verarbeiten")
    ap.add_argument("--csv", default="output.csv", help="CSV-Pfad")
    ap.add_argument("--airtable", action="store_true", help="Direkt in Airtable upserten")
    args = ap.parse_args()

    gemeinden = run_extraction(args.limit)
    for g in gemeinden:
        g.beschreibung_llm = generate_summary(g.to_dict())

    csv_path = to_csv(gemeinden, args.csv)
    print(f"[green]CSV geschrieben:[/] {csv_path}")
    if args.airtable:
        upsert_airtable(gemeinden)
        print("[green]Airtable-Sync fertig[/]")

if __name__ == "__main__":
    main()
