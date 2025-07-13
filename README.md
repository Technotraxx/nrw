# NRW Gemeinden Extractor (Verbesserte Version v0.3)

Ein robustes Streamlit‑basiertes Tool, das Wikipedia für jede Gemeinde und kreisfreie Stadt in Nordrhein‑Westfalen scrapt, jeden Eintrag mit LLM‑generierten Zusammenfassungen anreichert und das Ergebnis als CSV oder direkt zu Airtable exportiert.

## 🚀 Neue Features (v0.3)

- **✅ Robuste Fehlerbehandlung** mit Retry-Logik und Fallbacks
- **⚡ Parallele LLM-Verarbeitung** (3x schneller als vorher)
- **📊 Rich Progress-Bars** und Live-Status-Updates
- **🛡️ Umfassende Validierung** von Eingaben und Konfiguration
- **📈 Performance-Monitoring** und detaillierte Statistiken
- **🔧 Verbesserte CLI** mit Dry-Run-Modus und erweiterten Optionen

## 📋 Features

* **End‑to‑end Pipeline:** scrape → parse → optional Anthropic summary → export
* **Streamlit UI** mit interaktiven Fortschrittsanzeigen
* **Robuste CLI** für automatisierte Runs
* **Parallel Processing** für Wikipedia-Extraktion und LLM-Calls
* **Konfigurierbar** via **.env** file – keine hart-kodierten Secrets
* **Modulares Python Package** (`src/`) mit umfassender Fehlerbehandlung

## 🛠️ Installation

### Voraussetzungen
- Python 3.9+
- Internetverbindung für Wikipedia-Zugriff
- Optional: Anthropic API Key für LLM-Zusammenfassungen
- Optional: Airtable API Key für direkten Export

### Setup

```bash
# 1. Repository klonen
git clone <repository-url>
cd nrw-gemeinden-extractor

# 2. Virtual Environment erstellen
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Umgebungsvariablen konfigurieren
cp .env.example .env
# Dann .env mit deinen API Keys ausfüllen

# 5. Test-Run
python -m src.run_pipeline --limit 3 --verbose
```

## ⚙️ Konfiguration

Erstelle eine `.env` Datei basierend auf `.env.example`:

```bash
# === Scraper ===
USER_AGENT="NRW-Gemeinden-Extractor/0.2 (contact: you@example.com)"
MAX_WORKERS=5  # Anzahl paralleler Wikipedia-Requests

# === Anthropic (Optional) ===
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-sonnet-4-20250514
ANTHROPIC_MAX_TOKENS=1200

# === Airtable (Optional) ===
AIRTABLE_API_KEY=your_airtable_api_key_here
AIRTABLE_BASE_ID=your_base_id_here
AIRTABLE_TABLE_NAME=NRW_Gemeinden
```

## 🖥️ Verwendung

### Streamlit Web-Interface

```bash
streamlit run app.py
```

Dann öffne http://localhost:8501 in deinem Browser.

**Features der Web-UI:**
- 📊 System-Status-Dashboard
- ⚙️ Interaktive Konfiguration
- 📈 Live-Fortschrittsanzeigen
- 📥 Direkter CSV-Download
- 📋 Datenvorschau mit konfigurierbaren Spalten

### Kommandozeile (CLI)

```bash
# Basis-Verwendung: 10 Gemeinden ohne LLM
python -m src.run_pipeline --limit 10 --no-llm

# Vollständiger Run mit LLM (alle Gemeinden)
python -m src.run_pipeline --llm-workers 3

# Test-Modus (Dry-Run)
python -m src.run_pipeline --limit 5 --dry-run --verbose

# Export zu Airtable
python -m src.run_pipeline --limit 20 --airtable

# Hilfe anzeigen
python -m src.run_pipeline --help
```

**CLI-Optionen:**
- `--limit N`: Nur N Gemeinden verarbeiten
- `--no-llm`: LLM-Zusammenfassungen deaktivieren
- `--llm-workers N`: Anzahl paralleler LLM-Anfragen (1-5)
- `--csv path`: CSV-Ausgabepfad
- `--airtable`: Direkt zu Airtable hochladen
- `--verbose`: Detaillierte Ausgabe
- `--dry-run`: Simulation ohne echte Verarbeitung

## 📁 Projektstruktur

```
.
├── app.py                 # Streamlit Web-Interface
├── requirements.txt       # Python Dependencies
├── .env.example          # Umgebungsvariablen-Template
├── README.md             # Diese Datei
└── src/                  # Python Package
    ├── __init__.py       # Package-Definition
    ├── config.py         # Konfiguration mit Validierung
    ├── extract.py        # Wikipedia-Extraktion mit Retry-Logik
    ├── llm.py           # LLM-Integration mit Batch-Processing
    ├── export.py        # CSV/Airtable-Export mit Fehlerbehandlung
    └── run_pipeline.py  # CLI-Interface
```

## 🚀 Performance & Best Practices

### Empfohlene Einstellungen

- **MAX_WORKERS=5**: Guter Kompromiss zwischen Geschwindigkeit und Stabilität
- **LLM_WORKERS=3**: Vermeidet Rate-Limit-Probleme bei Anthropic
- **CHAR_LIMIT=10000**: Ausreichend für Zusammenfassungen, aber API-effizient

### Performance-Tipps

1. **Für Tests:** `--limit 3-10` verwenden
2. **Bei langsamer Verbindung:** `MAX_WORKERS=3` setzen
3. **Für große Datasets:** Erst ohne LLM testen, dann mit LLM
4. **Bei API-Limits:** `--llm-workers 1` verwenden

## 🐛 Troubleshooting

### Häufige Probleme

**❌ "LLM nicht verfügbar"**
```bash
# Lösung: API Key setzen
echo "ANTHROPIC_API_KEY=your_key_here" >> .env
```

**❌ "Airtable-Fehler"**
```bash
# Lösung: Airtable-Credentials prüfen
echo "AIRTABLE_API_KEY=your_key_here" >> .env
echo "AIRTABLE_BASE_ID=your_base_id_here" >> .env
```

**❌ "Timeout-Fehler"**
```bash
# Lösung: Worker reduzieren
echo "MAX_WORKERS=3" >> .env
```

**❌ "Memory-Probleme"**
```bash
# Lösung: Char-Limit reduzieren
python -m src.run_pipeline --char-limit 5000
```

### Debug-Modus

```bash
# Verbose-Ausgabe für Debugging
python -m src.run_pipeline --limit 3 --verbose

# Dry-Run für Konfigurationstests
python -m src.run_pipeline --dry-run --verbose
```

## 📊 Datenfelder

Jede Gemeinde wird mit folgenden Datenfeldern extrahiert:

| Feld | Beschreibung | Quelle |
|------|-------------|---------|
| `name` | Gemeindename | Wikipedia |
| `url` | Wikipedia-URL | Wikipedia |
| `einwohner` | Einwohnerzahl | Infobox |
| `einwohner_datum` | Stichtag der Einwohnerzahl | Infobox |
| `flaeche_km2` | Fläche in km² | Infobox |
| `hoehe_m` | Höhe über NN | Infobox |
| `gemeindeschluessel` | Amtlicher Gemeindeschlüssel | Infobox |
| `landkreis` | Landkreis | Infobox |
| `regierungsbezirk` | Regierungsbezirk | Infobox |
| `bundesland` | Bundesland | Infobox |
| `postleitzahl` | Postleitzahl(en) | Infobox |
| `vorwahl` | Telefonvorwahl | Infobox |
| `kfz_kennzeichen` | KFZ-Kennzeichen | Infobox |
| `koordinaten` | GPS-Koordinaten | Geo-Tags |
| `koordinaten_url` | GeoHack-Link | Geo-Tags |
| `website` | Offizielle Website | Infobox |
| `buergermeister` | Bürgermeister/in | Infobox |
| `full_text` | Wikipedia-Volltext (gekürzt) | Artikeltext |
| `beschreibung_llm` | KI-generierte Zusammenfassung | Anthropic |

## 🔧 Entwicklung

### Tests ausführen

```bash
# Unit Tests
pytest tests/

# Mit Coverage
pytest --cov=src tests/

# Linting
black src/ tests/
flake8 src/ tests/
mypy src/
```

### Neue Features entwickeln

1. **Branch erstellen:** `git checkout -b feature/new-feature`
2. **Tests schreiben:** Für neue Funktionen
3. **Code implementieren:** Mit umfassender Fehlerbehandlung
4. **Tests ausführen:** `pytest`
5. **Pull Request erstellen**

## 📄 Lizenz & Attribution

**Software:** MIT License

**Daten:** Content von Wikipedia ist lizenziert unter CC‑BY‑SA 4.0. Bitte entsprechend attributieren.

**Verwendung:** Dieses Tool ist für Forschungs‑ und Bildungszwecke gedacht. Bei kommerzieller Nutzung beachte bitte die Wikipedia-Nutzungsbedingungen.
