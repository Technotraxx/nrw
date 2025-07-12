"""Download & parse Wikipedia pages for NRW municipalities – volle Feldabdeckung."""
from __future__ import annotations
import re, time, requests
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from typing import Optional, Any, List, Tuple
import pandas as pd
from bs4 import BeautifulSoup
from rich.progress import track
from .config import Config

cfg = Config()
_session = requests.Session()
_session.headers.update({"User-Agent": cfg.user_agent})

# ------------------------------------------------------------------ #
# Datenmodell
# ------------------------------------------------------------------ #
@dataclass
class Gemeinde:
    name: str
    url: str
    # Infobox-Felder
    einwohner: Optional[str] = None
    flaeche_km2: Optional[str] = None
    hoehe_m: Optional[str] = None
    gemeindeschluessel: Optional[str] = None
    landkreis: Optional[str] = None
    regierungsbezirk: Optional[str] = None
    bundesland: Optional[str] = None
    postleitzahl: Optional[str] = None
    vorwahl: Optional[str] = None
    kfz_kennzeichen: Optional[str] = None
    koordinaten: Optional[str] = None
    website: Optional[str] = None
    buergermeister: Optional[str] = None
    # LLM
    beschreibung_llm: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

# ------------------------------------------------------------------ #
# Scraper-Hilfen
# ------------------------------------------------------------------ #
def _get(url: str) -> str:
    """HTTP-GET mit 3-fach Retry + Backoff."""
    for attempt in range(3):
        r = _session.get(url, timeout=30)
        if r.status_code == 200:
            return r.text
        time.sleep(2 * (attempt + 1))
    r.raise_for_status()

def _clean(text: str) -> str:
    return re.sub(r"\\[.*?\\]", "", text).strip()

LABEL_MAP = {
    "Einwohner": "einwohner",
    "Fläche": "flaeche_km2",
    "Höhe": "hoehe_m",
    "Gemeindeschlüssel": "gemeindeschluessel",
    "Landkreis": "landkreis",
    "Regierungsbezirk": "regierungsbezirk",
    "Bundesland": "bundesland",
    "Postleitzahl": "postleitzahl",
    "Vorwahl": "vorwahl",
    "Kfz": "kfz_kennzeichen",
    "KFZ": "kfz_kennzeichen",
    "Kfz-Kennzeichen": "kfz_kennzeichen",
    "Koordinaten": "koordinaten",
    "Website": "website",
    "Bürgermeister": "buergermeister",
}

WIKI_LIST_URL = (
    "https://de.wikipedia.org/wiki/"
    "Liste_der_St%C3%A4dte_und_Gemeinden_in_Nordrhein-Westfalen"
)

# ------------------------------------------------------------------ #
# Hauptfunktionen
# ------------------------------------------------------------------ #
def get_gemeinden_list() -> List[Tuple[str, str]]:
    html = _get(WIKI_LIST_URL)
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select("table.wikitable tbody tr td:first-child a")
    return [
        (
            a.get("title") or a["href"].split("/wiki/")[1].replace("_", " "),
            f"https://de.wikipedia.org{a['href']}",
        )
        for a in links
        if a["href"].startswith("/wiki/")
    ]

def parse_infobox(html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    box = soup.find(class_=re.compile("infobox"))
    data = {v: None for v in LABEL_MAP.values()}
    if not box:
        return data
    for row in box.select("tr"):
        h, v = row.find("th"), row.find("td")
        if not h or not v:
            continue
        header = _clean(h.get_text(" ", strip=True))
        value  = _clean(v.get_text(" ", strip=True))
        for label, attr in LABEL_MAP.items():
            if re.search(fr"^{label}", header, re.I):
                data[attr] = value
                break
    return data

def fetch_one(item: Tuple[str, str]) -> Gemeinde:
    name, url = item
    info = parse_infobox(_get(url))
    return Gemeinde(name=name, url=url, **info)

def run_extraction(limit: Optional[int] = None) -> list[Gemeinde]:
    items = get_gemeinden_list()
    if limit:
        items = items[:limit]
    results: list[Gemeinde] = []
    with ThreadPoolExecutor(max_workers=cfg.max_workers) as pool:
        for g in track(pool.map(fetch_one, items), total=len(items), description="Scraping"):
            results.append(g)
    return results
