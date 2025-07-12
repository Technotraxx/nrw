"""Streamlit UI for the NRW Gemeinden MVP."""
import streamlit as st
from pathlib import Path

from src.extract import run_extraction
from src.llm import generate_summary
from src.export import to_csv, upsert_airtable

st.title("🌆 NRW Gemeinden Extractor – MVP")

st.sidebar.header("Einstellungen")
max_items = st.sidebar.number_input("Anzahl Gemeinden (0 = alle)", min_value=0, max_value=400, value=0)
run_llm = st.sidebar.checkbox("LLM‑Zusammenfassung erzeugen")
upload_airtable = st.sidebar.checkbox("Direkt zu Airtable hochladen")

if st.button("🚀 Pipeline starten"):
    with st.spinner("Extrahiere Daten …"):
        results = run_extraction(max_items or None)
        if run_llm:
            for g in results:
                g.beschreibung_llm = generate_summary(g.to_dict())
        csv_path = to_csv(results, Path.cwd() / "output.csv")
        if upload_airtable:
            upsert_airtable(results)
    st.success("Fertig!")

    st.download_button(
        label="📥 CSV herunterladen",
        data=open(csv_path, "rb").read(),
        file_name="nrw_gemeinden.csv",
        mime="text/csv",
    )

    # Preview table
    import pandas as pd

    df = pd.DataFrame([g.to_dict() for g in results])
    st.dataframe(df)
