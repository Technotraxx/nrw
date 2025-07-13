"""NRW-Gemeinden – Scraper, Infobox-Parser & Volltext."""

from __future__ import annotations
import re, time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from typing import Any, List, Optional, Tuple
from urllib.parse import quote

import pandas as pd
import requests
from bs4 import BeautifulSoup
from rich.progress import track
from .config import Config

cfg = Config()
_session = requests.Session()
_session.headers.update({"User-Agent": cfg.user_agent})

# -------------------- Datenmodell --------------------
@dataclass
class Gemeinde:
    name: str; url: str
    einwohner: Optional[int] = None; einwohner_datum: Optional[str] = None
    flaeche_km2: Optional[float] = None; hoehe_m: Optional[int] = None
    gemeindeschluessel: Optional[str] = None
    landkreis: Optional[str] = None; regierungsbezirk: Optional[str] = None
    bundesland: Optional[str] = None
    postleitzahl: Optional[str] = None; vorwahl: Optional[str] = None
    kfz_kennzeichen: Optional[str] = None
    koordinaten: Optional[str] = None; koordinaten_url: Optional[str] = None
    website: Optional[str] = None; buergermeister: Optional[str] = None
    full_text: Optional[str] = None
    beschreibung_llm: Optional[str] = None
    def to_dict(self) -> dict[str, Any]: return asdict(self)

# -------------------- Helper --------------------
def _get(url: str) -> str:
    for att in range(3):
        r = _session.get(url, timeout=30)
        if r.ok: return r.text
        time.sleep(2 * (att + 1))
    r.raise_for_status()

def _lower_keys(df) -> dict[str, str]:
    out = {}
    for _, row in df.iterrows():
        if len(row) >= 2:
            k = str(row.iloc[0]).strip().lower().rstrip(":")
            v = str(row.iloc[1]).strip()
            out[k] = v
    return out

def _first(d, keys: list[str]) -> Optional[str]:
    for k in keys:
        if k in d: return d[k]
    return None

# -------------------- Parsing --------------------
def parse_page(name: str, url: str, char_limit: int) -> dict[str, Any]:
    info: dict[str, Any] = {}

    # -- Pandas-Infobox -----------------
    try:
        df = pd.read_html(url)[0]
        ib = _lower_keys(df)
    except Exception:
        ib = {}

    # Einwohner + Datum
    if (t := _first(ib, ["einwohner", "bevölkerung"])):
        if (m := re.search(r"([\d\.]+)", t)): info["einwohner"] = int(m[1].replace(".", ""))
        if (d := re.search(r"\(([^)]*)\)", t)): info["einwohner_datum"] = d[1]

    # Fläche / Höhe
    if (t := ib.get("fläche")) and (m := re.search(r"([\d,\.]+)", t)):
        info["flaeche_km2"] = float(m[1].replace(",", "."))
    if (t := ib.get("höhe")) and (m := re.search(r"(\d+)", t)):
        info["hoehe_m"] = int(m[1])

    # Direktfelder
    for key, attr in {
        "gemeindeschlüssel": "gemeindeschluessel",
        "landkreis": "landkreis",
        "regierungsbezirk": "regierungsbezirk",
        "bundesland": "bundesland",
        "postleitzahl": "postleitzahl",
        "vorwahl": "vorwahl",
        "kfz-kennzeichen": "kfz_kennzeichen",
    }.items():
        if key in ib: info[attr] = ib[key]

    # Website, Bürgermeister
    if (w := _first(ib, ["website", "homepage"])): info["website"] = w if w.startswith("http") else "https://" + w
    if (bm := _first(ib, ["bürgermeister", "oberbürgermeister"])): info["buergermeister"] = re.sub(r"\([^)]*\)", "", bm).strip()

    # -- BeautifulSoup für Koordinaten & Volltext ----
    html = _get(url)
    soup = BeautifulSoup(html, "html.parser")

    # Koordinaten & GeoHack-Link
    geo = soup.select_one("table.infobox span.geo")
    if geo:
        info["koordinaten"] = geo.text.strip()
        if geo.parent.name == "a": info["koordinaten_url"] = geo.parent["href"]
    # Fallback: erster externer geohack-Link
    if not info.get("koordinaten_url"):
        a = soup.find("a", href=re.compile("geohack"))
        if a: info["koordinaten_url"] = a["href"]

    # Volltext (ohne Infobox/Navbox)
    content = soup.find("div", class_="mw-parser-output")
    if content:
        for tag in content.find_all(["table", "div"], class_=re.compile("(infobox|navbox)")):
            tag.decompose()
        text = content.get_text(" ", strip=True)
        info["full_text"] = text[:char_limit]

    return info

# -------------------- Pipeline --------------------
LIST_URL = "https://de.wikipedia.org/wiki/Liste_der_Gemeinden_in_Nordrhein-Westfalen"
def get_gemeinden_list() -> List[Tuple[str, str]]:
    soup = BeautifulSoup(_get(LIST_URL), "html.parser")
    return [
        (a.get("title") or a["href"].split("/wiki/")[1].replace("_", " "),
         f"https://de.wikipedia.org{a['href']}")
        for a in soup.select("table.wikitable tbody tr td:first-child a")
        if a["href"].startswith("/wiki/")
    ]

def fetch_one(job: Tuple[str, str, int]) -> Gemeinde:
    name, url, cl = job
    return Gemeinde(name=name, url=url, **parse_page(name, url, cl))

def run_extraction(limit: Optional[int], char_limit: int) -> List[Gemeinde]:
    items = get_gemeinden_list()[:limit] if limit else get_gemeinden_list()
    jobs = [(n, u, char_limit) for n, u in items]
    with ThreadPoolExecutor(max_workers=cfg.max_workers) as pool:
        return list(track(pool.map(fetch_one, jobs), total=len(jobs), description="Scraping"))
