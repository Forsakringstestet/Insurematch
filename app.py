import streamlit as st
import pandas as pd
from utils.visualizer import render_comparison_table
from utils.enhanced_insurance_ui import display_pretty_summary
from parser import pdf_extractor, pdf_analyzer
from ai.openai_advisor import ask_openai, ask_openai_extract
from export import export_excel, export_pdf, export_word

# ✅ Måste vara först bland Streamlit-kommandon
st.set_page_config(
    page_title="Försäkringsanalys",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🌐 Anpassat tema (Streamlit themes styrs från .streamlit/config.toml)

# 🎛️ Sidopanel
st.sidebar.title("🔍 Försäkringsanalysverktyg")
st.sidebar.markdown("""
Analysera och jämför PDF-dokument som innehåller:
- Försäkringsbrev
- Offerter
- Villkor

Verktyget använder AI för att föreslå förbättringar och summera risker.
""")

industry = st.sidebar.selectbox("🏭 Välj bransch", [
    "Ingenjörsfirma", "IT-företag", "Tillverkande industri",
    "Bygg & Entreprenad", "Transport", "Handel", "Annan bransch"])

st.title("📄 Jämför & Analysera Försäkringsbrev, Offerter & Villkor")

uploaded_files = st.file_uploader(
    "📤 Ladda upp en eller flera PDF-filer", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    analysis_results = []

    for uploaded_file in uploaded_files:
        with st.spinner(f"🔎 Bearbetar {uploaded_file.name}..."):
            text = pdf_extractor.extract_text_from_pdf(uploaded_file)
            ai_data = ask_openai_extract(text, industry)  # 🧠 AI-driven extraktion med bransch

            if not ai_data or "fel" in ai_data:
                st.warning(f"⚠️ AI-extraktion misslyckades: {ai_data.get('fel') if isinstance(ai_data, dict) else 'Okänt fel'}")
                continue

            ai_data["score"] = pdf_analyzer.score_document(
                ai_data,
                vikt_omfattning=40,
                vikt_premie=30,
                vikt_självrisk=20,
                vikt_övrigt=10
            )

            analysis_results.append({
                "filename": uploaded_file.name,
                "data": ai_data
            })

            with st.expander(f"💬 AI-rådgivning för {uploaded_file.name}", expanded=False):
                ai_feedback = ask_openai(ai_data, industry)
                st.markdown(ai_feedback)

    if analysis_results:
        st.markdown("""
        ## 📊 Jämförelsetabell med färgkodning
        """)
        render_comparison_table(analysis_results)

        st.markdown("""
        ## 📑 Sammanställning & Jämförelse
        """)
        display_pretty_summary(analysis_results)

        st.download_button(
            "📥 Exportera resultat som Excel",
            export_excel.export_summary_excel(analysis_results),
            file_name="forsakringsjamforelse.xlsx")

        st.download_button(
            "📄 Exportera som PDF",
            export_pdf.export_summary_pdf(analysis_results),
            file_name="forsakringsjamforelse.pdf")

        st.download_button(
            "📝 Exportera som Word",
            export_word.generate_procurement_word(analysis_results),
            file_name="upphandlingsunderlag.docx")
