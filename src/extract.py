"""Functions to fetch and parse Wikipedia pages for NRW municipalities."""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from typing import Any, Iterable

import pandas as pd
import requests
from bs4 import BeautifulSoup
from rich.progress import track

from .config import Config

WIKI_BASE = "https://de.wikipedia.org/wiki/"

cfg = Config()

###############################################################################
# Data Model
###############################################################################

@dataclass
class Gemeinde:
    """Structured representation of a NRW municipality."""

    name: str
    url: str
    einwohner: str | None = None
    flaeche_km2: str | None = None
    hoehe_m: str | None = None
    beschreibung_llm: str | None = None  # filled later

    def to_dict(self) -> dict[str, Any]:
        """Convert dataclass to plain dict for CSV/JSON export."""
        return asdict(self)

###############################################################################
# Helpers
###############################################################################

_session = requests.Session()
_session.headers.update({"User-Agent": cfg.user_agent})


def _get(url: str) -> str:
    """HTTP GET with simple retry and politeness delay."""
    for attempt in range(3):
        resp = _session.get(url, timeout=20)
        if resp.status_code == 200:
            return resp.text
        time.sleep(2 * (attempt + 1))
    resp.raise_for_status()


def clean_name(raw: str) -> str:
    """Convert wiki‑URL fragment to plain text name."""
    return raw.replace("_", " ")

###############################################################################
# Core logic
###############################################################################

def get_gemeinden_list() -> list[tuple[str, str]]:
    """Return list of (name, url) tuples for all municipalities & independent cities in NRW.

    Source page: https://de.wikipedia.org/wiki/Liste_der_St%C3%A4dte_und_Gemeinden_in_Nordrhein-Westfalen
    """
    list_url = (
        "https://de.wikipedia.org/wiki/"  # base
        "Liste_der_St%C3%A4dte_und_Gemeinden_in_Nordrhein-Westfalen"
    )
    html = _get(list_url)
    soup = BeautifulSoup(html, "html.parser")

    # The table rows contain links to municipality pages
    rows = soup.select("table.wikitable tbody tr td:first-child a")
    items: list[tuple[str, str]] = []
    for a in rows:
        href = a.get("href")
        if not href or not href.startswith("/wiki/"):
            continue
        title = a.get("title") or clean_name(href.split("/wiki/")[1])
        items.append((title, f"https://de.wikipedia.org{href}"))
    return items


def parse_infobox(html: str) -> dict[str, str | None]:
    """Extract selected fields from Wikipedia infobox (very lightweight)."""
    soup = BeautifulSoup(html, "html.parser")
    info: dict[str, str | None] = {
        "einwohner": None,
        "flaeche_km2": None,
        "hoehe_m": None,
    }
    box = soup.find(class_=re.compile("infobox"))
    if not box:
        return info
    rows = box.select("tr")
    for r in rows:
        header = (r.find("th") or {}).get_text(strip=True) if r.find("th") else ""
        data = (r.find("td") or {}).get_text(" ", strip=True) if r.find("td") else ""
        if "Einwohner" in header:
            info["einwohner"] = data.split()[0]
        elif "Fläche" in header:
            info["flaeche_km2"] = data.split()[0]
        elif "Höhe" in header:
            info["hoehe_m"] = data.split()[0]
    return info


def fetch_one(item: tuple[str, str]) -> Gemeinde:
    """Fetch and parse a single municipality, returning a populated Gemeinde."""
    name, url = item
    html = _get(url)
    details = parse_infobox(html)
    return Gemeinde(name=name, url=url, **details)


def run_extraction(max_items: int | None = None) -> list[Gemeinde]:
    """High‑level extraction orchestrator.

    Args:
        max_items: limit number of municipalities (for quick tests).
    """
    items = get_gemeinden_list()
    if max_items:
        items = items[:max_items]

    gemeinden: list[Gemeinde] = []
    with ThreadPoolExecutor(max_workers=cfg.max_workers) as pool:
        for g in track(pool.map(fetch_one, items), total=len(items), description="Scraping"):
            gemeinden.append(g)
    return gemeinden
