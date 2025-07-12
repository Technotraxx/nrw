"""CLI entry‑point for headless runs (without Streamlit)."""
import argparse
from pathlib import Path

from rich import print

from .extract import run_extraction
from .llm import generate_summary
from .export import to_csv, upsert_airtable


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NRW Gemeinden pipeline")
    parser.add_argument("--limit", type=int, help="Process only N items (debug)")
    parser.add_argument("--csv", default="output.csv", help="Path for CSV export")
    parser.add_argument("--airtable", action="store_true", help="Also push to Airtable")
    args = parser.parse_args()

    gemeinden = run_extraction(args.limit)

    # Generate LLM summaries if key available
    for g in gemeinden:
        g.beschreibung_llm = generate_summary(g.to_dict())

    csv_path = to_csv(gemeinden, args.csv)
    print(f"CSV written to [bold]{csv_path}[/]")

    if args.airtable:
        upsert_airtable(gemeinden)
        print("Airtable sync done.")


if __name__ == "__main__":
    main()
