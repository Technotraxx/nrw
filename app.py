"""Streamlit-Frontend für interaktive Nutzung (mit Zeichenlimit-Eingabe)."""
import streamlit as st
from pathlib import Path
import pandas as pd

from src.extract import run_extraction
from src.llm import generate_summary
from src.export import to_csv, upsert_airtable

st.set_page_config(page_title="NRW Gemeinden Extractor", page_icon="🌆", layout="wide")
st.title("🌆 NRW Gemeinden Extractor – MVP")

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Einstellungen")
    limit = st.number_input("Anzahl Gemeinden (0 = alle)", 0, 400, 3)
    char_limit = st.number_input("Zeichenlimit Volltext", 1000, 20000, 10000, step=1000)
    do_llm = st.checkbox("LLM-Zusammenfassung erzeugen", True)
    do_airtable = st.checkbox("Direkt zu Airtable hochladen")

# ---------- Button ----------
if st.button("🚀 Pipeline starten"):
    with st.spinner("Extrahiere Wikipedia …"):
        results = run_extraction(limit or None, char_limit)
        if do_llm:
            for g in results:
                g.beschreibung_llm = generate_summary(g.to_dict())

        csv_path = to_csv(results, Path("output.csv"))
        if do_airtable:
            upsert_airtable(results)

    st.success("Fertig!")

    st.download_button(
        "📥 CSV herunterladen",
        data=open(csv_path, "rb").read(),
        file_name="nrw_gemeinden.csv",
        mime="text/csv",
    )

    st.dataframe(pd.DataFrame([g.to_dict() for g in results]), use_container_width=True)
