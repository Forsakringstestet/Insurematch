import streamlit as st
import pandas as pd
import json
import re
from io import BytesIO
from docx import Document
from PyPDF2 import PdfReader

# === Funktioner ===

def to_number(varde):
    if varde is None:
        return 0
    s = str(varde).replace(" ", "").replace("kr", "").replace("SEK", "").replace("k", "000").replace("MSEK", "000000")
    digits = ''.join(filter(str.isdigit, s))
    return int(digits) if digits else 0

def extrahera_belopp(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return "0"

def extrahera_lista(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def extrahera_villkor_ur_pdf(text):
    return {
        "försäkringsgivare": "Okänt",
        "egendom": extrahera_belopp(text, r"(egendom|byggnad|fastighet).*?(\d+[\s]*[MmKk]?[\s]*SEK|kr)"),
        "ansvar": extrahera_belopp(text, r"(ansvar|skadestånd).*?(\d+[\s]*[MmKk]?[\s]*SEK|kr)"),
        "avbrott": extrahera_belopp(text, r"(avbrott|förlust av intäkt|driftstopp).*?(\d+[\s]*[MmKk]?[\s]*SEK|kr)"),
        "självrisk": extrahera_belopp(text, r"(självrisk|självrisken).*?(\d+[\s]*[MmKk]?[\s]*SEK|kr)"),
        "undantag": extrahera_lista(text, r"(undantag|exkluderat).*?:\s*(.*?)(\n|$)"),
        "premie": extrahera_belopp(text, r"(premie|försäkringsbelopp).*?(\d+[\s]*[MmKk]?[\s]*SEK|kr)"),
        "villkorsreferens": "PDF"
    }

def läs_pdf_text(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def generera_word_dokument(data):
    doc = Document()
    doc.add_heading("Upphandlingsunderlag – Försäkringsjämförelse", level=1)
    table = doc.add_table(rows=1, cols=len(data[0]))
    hdr_cells = table.rows[0].cells
    for i, key in enumerate(data[0].keys()):
        hdr_cells[i].text = key
    for row in data:
        cells = table.add_row().cells
        for i, key in enumerate(row):
            cells[i].text = str(row[key])
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# === App-gränssnitt ===

st.set_page_config(page_title="Försäkringsguide", page_icon="🛡️", layout="centered")
st.title("🛡️ Försäkringsguide och Jämförelse")

menu = st.sidebar.radio("Navigera", ["🔍 Automatisk analys", "✍️ Manuell inmatning & rekommendation"])

if menu == "🔍 Automatisk analys":
    uploaded_pdf = st.file_uploader("📄 Ladda upp försäkringsbrev/villkor (PDF)", type="pdf")
    if uploaded_pdf:
        text = läs_pdf_text(uploaded_pdf)
        st.subheader("🔎 Extraherad text (förhandsvisning):")
        st.text_area("PDF-innehåll", value=text[:3000], height=300)
        villkor = extrahera_villkor_ur_pdf(text)
        st.subheader("📋 Extraherade värden:")
        st.json(villkor)
        tomma_fält = [k for k, v in villkor.items() if to_number(v) == 0 and k != "undantag"]
        if tomma_fält:
            st.warning(f"⚠️ Följande fält kunde inte hittas i PDF: {', '.join(tomma_fält)}")
        st.success("✅ Villkorsdata färdig att användas!")
        st.download_button("⬇️ Exportera till Word", data=generera_word_dokument([villkor]), file_name="upphandlingsunderlag.docx")

elif menu == "✍️ Manuell inmatning & rekommendation":
    with st.form("företagsformulär"):
        st.subheader("🏢 Företagsinformation")
        företagsnamn = st.text_input("Företagsnamn")
        orgnr = st.text_input("Organisationsnummer")
        omsättning = st.number_input("Omsättning (MSEK)", min_value=0.0, step=0.1)
        anställda = st.number_input("Antal anställda", min_value=0, step=1)
        bransch = st.selectbox("Bransch", ["IT", "Tillverkning", "Transport", "Konsult", "Handel", "Bygg", "Vård"])
        ort = st.text_input("Stad")
        land = st.text_input("Land", value="Sverige")
        nuvarande = st.text_input("Nuvarande försäkringsbolag (valfritt)")
        
        st.subheader("🛡️ Försäkringsmoment")
        egendom = st.number_input("Egendomsvärde (kr)", step=10000)
        ansvar = st.number_input("Ansvarsskydd (kr)", step=10000)
        avbrott = st.number_input("Avbrottsersättning (kr)", step=10000)
        premie = st.number_input("Premie per år (kr)", step=10000)
        submitted = st.form_submit_button("Analysera")

    if submitted:
        st.success(f"🎯 Tack {företagsnamn}, analys för bransch: {bransch}")
        rekommendation = f"🔎 För ett företag inom {bransch.lower()} med {anställda} anställda och {omsättning} MSEK i omsättning rekommenderas vanligtvis följande försäkringsmoment:

"

        if bransch == "IT":
            rekommendation += "- Cyberförsäkring (5–15% av omsättningen)
- Konsultansvar (2–10 MSEK)
- Egendomsskydd för IT-utrustning"
        elif bransch == "Tillverkning":
            rekommendation += "- Egendomsförsäkring för maskiner/lager
- Produktansvar (minst 10 MSEK)
- Avbrottsförsäkring (upp till 12 månaders täckning)"
        elif bransch == "Transport":
            rekommendation += "- Transportöransvar & varuförsäkring
- Trafik/vagnskada på fordon
- Avbrott & ansvar utanför CMR"
        elif bransch == "Konsult":
            rekommendation += "- Konsultansvar (minst 2–5 MSEK)
- Rättsskydd
- Cyber om kunddata hanteras"
        elif bransch == "Handel":
            rekommendation += "- Lager/inventarieförsäkring
- Produktansvar (säljled)
- Avbrott & transport"
        elif bransch == "Bygg":
            rekommendation += "- Entreprenad/allrisk
- ROT-ansvar
- Egendom/maskiner + ansvarsförsäkring"
        elif bransch == "Vård":
            rekommendation += "- Patientförsäkring (lagkrav)
- Avbrott & egendom
- Ansvar utöver patientskadelagen"

        st.markdown(f"""
#### 📌 Rekommenderat försäkringsupplägg
{rekommendation}
""")

        st.download_button("⬇️ Exportera förslag (Word)", data=generera_word_dokument([{
            "Företag": företagsnamn,
            "Org.nr": orgnr,
            "Bransch": bransch,
            "Egendom": egendom,
            "Ansvar": ansvar,
            "Avbrott": avbrott,
            "Premie": premie,
            "Ort": ort,
            "Land": land,
            "Rekommendation": rekommendation
        }]), file_name="forsakringsrekommendation.docx")
