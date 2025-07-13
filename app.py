"""Streamlit-Frontend mit verbesserter Fehlerbehandlung und Performance."""
import streamlit as st
import pandas as pd
import logging
from pathlib import Path
from typing import List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from src.extract import run_extraction, Gemeinde, ScrapingError
    from src.llm import generate_summaries_batch, is_available as llm_available, get_model_info
    from src.export import to_csv, upsert_airtable
    from src.config import Config
except ImportError as e:
    st.error(f"Fehler beim Laden der Module: {e}")
    st.stop()

# Konfiguration laden
cfg = Config()

# Streamlit Konfiguration
st.set_page_config(
    page_title="NRW Gemeinden Extractor",
    page_icon="🌆",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🌆 NRW Gemeinden Extractor – Verbesserte Version")

# Status-Informationen
with st.expander("📊 System Status", expanded=False):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Max Workers", cfg.max_workers)
    
    with col2:
        llm_status = "✅ Verfügbar" if llm_available() else "❌ Nicht verfügbar"
        st.metric("LLM Status", llm_status)
    
    with col3:
        airtable_status = "✅ Konfiguriert" if cfg.has_airtable_config else "❌ Nicht konfiguriert"
        st.metric("Airtable", airtable_status)
    
    if llm_available():
        model_info = get_model_info()
        st.info(f"🤖 LLM Modell: {model_info['model']} (Max Tokens: {model_info['max_tokens']})")

# Sidebar für Einstellungen
with st.sidebar:
    st.header("⚙️ Einstellungen")
    
    # Basis-Einstellungen
    st.subheader("Extraktion")
    limit = st.number_input(
        "Anzahl Gemeinden (0 = alle)", 
        min_value=0, 
        max_value=400, 
        value=3,
        help="Begrenzt die Anzahl der zu verarbeitenden Gemeinden. Nützlich für Tests."
    )
    
    char_limit = st.number_input(
        "Zeichenlimit Volltext", 
        min_value=1000, 
        max_value=20000, 
        value=10000, 
        step=1000,
        help="Maximale Länge des extrahierten Wikipedia-Textes pro Gemeinde."
    )
    
    # LLM-Einstellungen
    st.subheader("LLM-Zusammenfassung")
    do_llm = st.checkbox(
        "LLM-Zusammenfassung erzeugen", 
        value=llm_available(),
        disabled=not llm_available(),
        help="Generiert automatische Zusammenfassungen mit KI. Benötigt Anthropic API Key."
    )
    
    if do_llm and llm_available():
        llm_workers = st.slider(
            "LLM Worker (parallel)", 
            min_value=1, 
            max_value=5, 
            value=3,
            help="Anzahl paralleler LLM-Anfragen. Mehr = schneller, aber höhere Rate Limit Gefahr."
        )
    else:
        llm_workers = 3
    
    # Export-Einstellungen
    st.subheader("Export")
    do_airtable = st.checkbox(
        "Direkt zu Airtable hochladen",
        value=False,
        disabled=not cfg.has_airtable_config,
        help="Lädt Daten direkt in Airtable hoch. Benötigt Airtable API Konfiguration."
    )

# Hauptbereich
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("🚀 Pipeline")
    
    # Pipeline-Button
    if st.button("Pipeline starten", type="primary", use_container_width=True):
        
        # Validierung der Eingaben
        if limit == 0:
            st.info("ℹ️ Verarbeite ALLE NRW-Gemeinden. Dies kann 30+ Minuten dauern.")
        
        # Progress Container
        progress_container = st.container()
        
        try:
            with progress_container:
                # Schritt 1: Wikipedia-Extraktion
                st.write("📄 **Schritt 1:** Wikipedia-Daten extrahieren...")
                
                with st.spinner("Lade Gemeinden-Liste und extrahiere Daten..."):
                    extraction_progress = st.progress(0)
                    status_text = st.empty()
                    
                    # Extraction mit Fortschrittsanzeige
                    try:
                        results: List[Gemeinde] = run_extraction(
                            limit=limit if limit > 0 else None, 
                            char_limit=char_limit
                        )
                        extraction_progress.progress(100)
                        status_text.success(f"✅ {len(results)} Gemeinden erfolgreich extrahiert")
                        
                    except ScrapingError as e:
                        st.error(f"❌ Fehler bei der Extraktion: {e}")
                        st.stop()
                    except Exception as e:
                        st.error(f"❌ Unerwarteter Fehler: {e}")
                        logger.error(f"Extraction error: {e}", exc_info=True)
                        st.stop()
                
                # Schritt 2: LLM-Zusammenfassungen (optional)
                if do_llm and results:
                    st.write("🤖 **Schritt 2:** LLM-Zusammenfassungen generieren...")
                    
                    with st.spinner(f"Generiere Zusammenfassungen mit {llm_workers} parallel Workers..."):
                        llm_progress = st.progress(0)
                        llm_status = st.empty()
                        
                        try:
                            # Konvertiere zu Dictionaries für Batch-Verarbeitung
                            gemeinde_dicts = [g.to_dict() for g in results]
                            
                            # Batch-Verarbeitung
                            summaries = generate_summaries_batch(
                                gemeinde_dicts, 
                                max_workers=llm_workers
                            )
                            
                            # Füge Zusammenfassungen zu Gemeinde-Objekten hinzu
                            successful_summaries = 0
                            for i, (gemeinde, summary) in enumerate(zip(results, summaries)):
                                gemeinde.beschreibung_llm = summary
                                if summary:
                                    successful_summaries += 1
                                llm_progress.progress((i + 1) / len(results))
                            
                            llm_status.success(f"✅ {successful_summaries}/{len(results)} Zusammenfassungen generiert")
                            
                        except Exception as e:
                            st.warning(f"⚠️ Fehler bei LLM-Verarbeitung: {e}")
                            logger.error(f"LLM error: {e}", exc_info=True)
                
                # Schritt 3: Export
                st.write("💾 **Schritt 3:** Daten exportieren...")
                
                try:
                    # CSV Export
                    csv_path = to_csv(results, Path("output.csv"))
                    st.success(f"✅ CSV erstellt: {csv_path}")
                    
                    # Airtable Export (optional)
                    if do_airtable:
                        with st.spinner("Lade zu Airtable hoch..."):
                            upsert_airtable(results)
                            st.success("✅ Airtable-Upload abgeschlossen")
                    
                except Exception as e:
                    st.error(f"❌ Export-Fehler: {e}")
                    logger.error(f"Export error: {e}", exc_info=True)
            
            # Erfolgsmeldung
            st.balloons()
            st.success("🎉 Pipeline erfolgreich abgeschlossen!")
            
            # Download-Button
            try:
                with open(csv_path, "rb") as file:
                    st.download_button(
                        label="📥 CSV herunterladen",
                        data=file.read(),
                        file_name=f"nrw_gemeinden_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"❌ Download-Fehler: {e}")
            
            # Datenvorschau
            if results:
                st.subheader("📊 Datenvorschau")
                
                # Statistiken
                stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
                
                with stats_col1:
                    st.metric("Gemeinden", len(results))
                
                with stats_col2:
                    avg_pop = sum(g.einwohner for g in results if g.einwohner) / len([g for g in results if g.einwohner])
                    st.metric("Ø Einwohner", f"{avg_pop:,.0f}")
                
                with stats_col3:
                    with_llm = sum(1 for g in results if g.beschreibung_llm)
                    st.metric("Mit LLM", f"{with_llm}/{len(results)}")
                
                with stats_col4:
                    total_area = sum(g.flaeche_km2 for g in results if g.flaeche_km2)
                    st.metric("Gesamtfläche", f"{total_area:,.1f} km²")
                
                # Tabelle
                df = pd.DataFrame([g.to_dict() for g in results])
                
                # Formatiere Zahlen für bessere Lesbarkeit
                if 'einwohner' in df.columns:
                    df['einwohner'] = df['einwohner'].apply(lambda x: f"{x:,}" if pd.notna(x) else "")
                
                if 'flaeche_km2' in df.columns:
                    df['flaeche_km2'] = df['flaeche_km2'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
                
                # Zeige Tabelle mit konfigurierbaren Spalten
                columns_to_show = st.multiselect(
                    "Anzuzeigende Spalten auswählen:",
                    options=df.columns.tolist(),
                    default=['name', 'einwohner', 'landkreis', 'regierungsbezirk', 'website']
                )
                
                if columns_to_show:
                    st.dataframe(
                        df[columns_to_show], 
                        use_container_width=True,
                        height=400
                    )
                else:
                    st.dataframe(df, use_container_width=True, height=400)
                
        except Exception as e:
            st.error(f"❌ Unerwarteter Pipeline-Fehler: {e}")
            logger.error(f"Pipeline error: {e}", exc_info=True)

with col_right:
    st.subheader("ℹ️ Information")
    
    st.info("""
    **Über dieses Tool:**
    
    Dieses Tool extrahiert strukturierte Daten über alle Gemeinden und kreisfreien Städte in Nordrhein-Westfalen aus Wikipedia.
    
    **Features:**
    - 🔍 Automatische Wikipedia-Extraktion
    - 🤖 KI-generierte Zusammenfassungen  
    - 📊 CSV & Airtable Export
    - 🚀 Parallele Verarbeitung
    - 📈 Fortschrittsanzeige
    
    **Tipp:** Starte mit einer kleinen Anzahl (3-10) zum Testen!
    """)
    
    # Hilfe-Sektion
    with st.expander("🆘 Hilfe & Troubleshooting"):
        st.markdown("""
        **Häufige Probleme:**
        
        1. **LLM nicht verfügbar:** Prüfe ANTHROPIC_API_KEY in .env
        2. **Airtable-Fehler:** Prüfe AIRTABLE_API_KEY und BASE_ID
        3. **Langsame Performance:** Reduziere max_workers in .env
        4. **Timeout-Fehler:** Internetverbindung prüfen
        
        **Performance-Tipps:**
        - Verwende 3-5 max_workers für stabilen Betrieb
        - LLM-Verarbeitung ist der langsamste Schritt
        - Bei großen Datenmengen: erst ohne LLM testen
        """)

# Footer
st.markdown("---")
st.markdown("🏛️ **Datenquelle:** Wikipedia | 📄 **Lizenz:** CC-BY-SA 4.0")
