
import streamlit as st
from datetime import date, timedelta
import pdfplumber
import Forsakrings_Parser as parser

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
            parsed = parser.extrahera_th_forsakring(text)
        elif "gjensidige" in text or "lf" in file.name.lower():
            parsed = parser.extrahera_lf_forsakring(text)
        else:
            parsed = parser.extrahera_if_forsakring(text)

        data.append(parsed)
        st.markdown(f"### 📄 {file.name}")
        st.json(parsed)
        st.markdown("---")

    df, benchmark = parser.poangsatt_villkor(data)
    parser.render_resultat(df, benchmark, st)
    st.success(f"🔔 Lägg in {paminnelse_datum} i din kalender!")
