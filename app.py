
import streamlit as st
from datetime import date, timedelta
import pdfplumber
from Forsakrings_Parser import (
    extrahera_if_forsakring,
    extrahera_lf_forsakring,
    extrahera_th_forsakring,
    poangsatt_villkor,
    render_resultat
)

st.set_page_config(page_title="Försäkringsguide", page_icon="🛡️", layout="centered")
st.title("🛡️ Försäkringsguide & Jämförelse")

uploaded_files = st.file_uploader("📂 Ladda upp PDF:er", type="pdf", accept_multiple_files=True)
paminnelse_datum = st.date_input("🔔 Påminnelse om förnyelse", value=date.today() + timedelta(days=300))

if uploaded_files:
    data = []
    for file in uploaded_files:
        with pdfplumber.open(file) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages]).lower()
        if "trygg-hansa" in text:
            parsed = extrahera_th_forsakring(text)
        elif "gjensidige" in text or "lf" in file.name.lower():
            parsed = extrahera_lf_forsakring(text)
        else:
            parsed = extrahera_if_forsakring(text)
        data.append(parsed)
        st.markdown(f"### 📄 {file.name}")
        st.json(parsed)
        st.markdown("---")
    df, benchmark = poangsatt_villkor(data)
    render_resultat(df, benchmark, st)
    st.success(f"🔔 Lägg in {paminnelse_datum} i din kalender!")
