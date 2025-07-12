# NRW Gemeinden Extractor (MVP)

A minimal Streamlit‑based tool that scrapes Wikipedia for every municipality & independent city in North‑Rhine Westphalia, enriches each entry with an LLM‑generated summary, and exports the result as CSV or directly to Airtable.

### Features
* End‑to‑end pipeline: scrape → parse → optional Anthropic summary → export
* Streamlit UI to kick off runs and download results
* Configurable via **.env** file – no hard‑coded secrets
* Modular Python package (`src/`) ready for unit tests later

### Quick Start
```bash
# 1. Clone repo & install deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Set secrets
cp .env.example .env  # then fill in API keys

# 3. Run Streamlit app
streamlit run app.py
