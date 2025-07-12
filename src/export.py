"""CSV- und Airtable-Export."""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterable
from pyairtable import Table
from .config import Config
from .extract import Gemeinde

cfg = Config()

def to_csv(rows: list[Gemeinde], path: str | Path = "output.csv") -> Path:
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].to_dict().keys())
        writer.writeheader()
        for g in rows:
            writer.writerow(g.to_dict())
    return path

def upsert_airtable(rows: list[Gemeinde]) -> None:
    if not (cfg.airtable_key and cfg.airtable_base_id):
        print("[export] Airtable-Credentials fehlen – Überspringe Upload.")
        return
    table = Table(cfg.airtable_key, cfg.airtable_base_id, cfg.airtable_table_name)
    for g in rows:
        table.upsert(match_field="name", record=g.to_dict())
