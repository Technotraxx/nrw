"""Utilities to write results to CSV and/or Airtable."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from pyairtable import Table  # type: ignore

from .config import Config
from .extract import Gemeinde

cfg = Config()


def to_csv(rows: Iterable[Gemeinde], path: str | Path = "output.csv") -> Path:
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].to_dict().keys())
        writer.writeheader()
        for g in rows:
            writer.writerow(g.to_dict())
    return path


def upsert_airtable(rows: Iterable[Gemeinde]) -> None:
    """Push each row to Airtable, creating or updating by `name`."""
    if not all([cfg.airtable_key, cfg.airtable_base_id]):
        print("[export] Airtable creds missing – skipping.")
        return

    table = Table(cfg.airtable_key, cfg.airtable_base_id, cfg.airtable_table_name)
    for g in rows:
        table.upsert("name", g.to_dict())
