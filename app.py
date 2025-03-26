import streamlit as st
import pandas as pd
import json
import re
from io import BytesIO
from docx import Document
from PyPDF2 import PdfReader
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import date, timedelta

# === Funktioner ===

# För att omvandla strängar till numeriska värden för beräkningar.
def to_number(varde):
    try:
        if varde is None:
            return 0
        if isinstance(varde, (int, float)):
            return int(varde)
        s = str(varde).lower()
        s = s.replace(" ", "").replace("kr", "").replace("sek", "").replace(",", ".")
        if "msek" in s:
            return int(float(s.replace("msek", "")) * 1_000_000)
        elif "m" in s:
            return int(float(s.replace("m", "")) * 1_000_000)
        elif "k" in s:
            return int(float(s.replace("k", "")) * 1_000)
        digits = ''.join(filter(str.isdigit, s))
        return int(digits) if digits else 0
    except Exception as e:
        return 0

# Extrahera specifika belopp från texten.
def extrahera_belopp(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return "0"

# Extrahera listor (t.ex. undantag) från texten.
def extrahera_lista(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

# Extrahera försäkringsgivare från texten
def extrahera_forsakringsgivare(text):
    match = re.search(r"(if|lf|trygg-hansa|moderna|protector|svedea|folksam|gjensidige|dina|lanförsäkringar)", text, re.IGNORECASE)
    if match:
        return match.group(1).capitalize()
    return "Okänt"

# Funktion för att extrahera alla villkor från en PDF-fil
def extrahera_villkor_ur_pdf(text):
    return {
        "försäkringsgivare": extrahera_forsakringsgivare(text),
        "egendom": extrahera_belopp(text, r"(egendom|byggnad|fastighet).*?(\d+[\s]*[MmKkMmSEKsek,\.]*[\s]*SEK|kr)"),
        "ansvar": extrahera_belopp(text, r"(ansvar|skadestånd).*?(\d+[\s]*[MmKkMmSEKsek,\.]*[\s]*SEK|kr)"),
        "avbrott": extrahera_belopp(text, r"(avbrott|förlust av intäkt|driftstopp).*?(\d+[\s]*[MmKkMmSEKsek,\.]*[\s]*SEK|kr)"),
        "självrisk": extrahera_belopp(text, r"(självrisk|självrisken).*?(\d+[\s]*[MmKkMmSEKsek,\.]*[\s]*SEK|kr)"),
        "undantag": extrahera_lista(text, r"(undantag|exkluderat).*?:\s*(.*?)(\n|$)"),
        "premie": extrahera_belopp(text, r"(premie|försäkringsbelopp).*?(\d+[\s]*[MmKkMmSEKsek,\.]*[\s]*SEK|kr)"),
        "villkorsreferens": "PDF"
    }

# Format för att presentera extraherad text från PDF
def formattera_pdf_text(text):
    text = re.sub(r"(?<=\w)\n(?=\w)", " ", text)
    stycken = re.split(r"\n{2,}|(?=\n[A-ZÄÖÅ])", text)
    highlight_nyckelord = [
        (r"(?i)(självrisk)", "🟡 \\1"),
        (r"(?i)(egendom)", "🟢 \\1"),
        (r"(?i)(ansvar)", "🟣 \\1"),
        (r"(?i)(avbrott)", "🔵 \\1"),
        (r"(?i)(undantag)", "🔴 \\1"),
        (r"(?i)(premie)", "🟠 \\1")
    ]
    formatterad = "\n\n".join([stycke.strip() for stycke in stycken if stycke.strip()])
    for pattern, emoji in highlight_nyckelord:
        formatterad = re.sub(pattern, emoji, formatterad)
    return formatterad

# === Streamlit-gränssnitt ===
st.set_page_config(page_title="Försäkringsguide", page_icon="🛡️", layout="centered")
st.title("🛡️ Försäkringsguide och Jämförelse")

menu = st.sidebar.radio("Navigera", ["🔍 Automatisk analys", "✍️ Manuell inmatning & rekommendation"])

# Automatisk analys
if menu == "🔍 Automatisk analys":
    uploaded_pdfs = st.file_uploader(
    "📄 Ladda upp en eller flera PDF:er", key="upload_pdfs", type="pdf", accept_multiple_files=True)
    påminnelse_datum = st.date_input(
    "🔔 Vill du få en påminnelse innan förnyelse?", value=date.today() + timedelta(days=300), key="reminder_date")

    if uploaded_pdfs:
        villkorslista = []
        st.markdown("### 📂 Tidigare jämförelser:")

        for i, pdf in enumerate(uploaded_pdfs):
            text = läs_pdf_text(pdf)
            st.markdown(f"#### 📄 Fil {i+1}: {pdf.name}")
            st.text_area(f"Innehåll ur {pdf.name}", value=text[:2000], height=200)

            extrakt = extrahera_villkor_ur_pdf(text)
            villkorslista.append(extrakt)

            st.json(extrakt)
            saknade = [k for k, v in extrakt.items() if to_number(v) == 0 and k != "undantag"]
            if saknade:
                st.warning(f"⚠️ Saknade fält i {pdf.name}: {', '.join(saknade)}")
            st.markdown("---")

        if villkorslista:
            df = pd.DataFrame(poangsatt_villkor(villkorslista))
            st.subheader("📊 Jämförelse med poängsättning")

            st.dataframe(df.style.applymap(färgschema, subset=["Totalpoäng"]))

            st.markdown("### 📉 Benchmarking")
            st.markdown(f"**Snittpremie:** {df['Premie'].mean():,.0f} kr  |  **Snittsjälvrisk:** {df['Självrisk'].mean():,.0f} kr  |  **Snittpoäng:** {df['Totalpoäng'].mean():.2f}")

            st.download_button("⬇️ Ladda ner sammanställning (Word)", data=generera_word_dokument(df.to_dict(orient="records")), file_name="jamforelse_upphandling.docx")

            st.success(f"🔔 Påminnelse noterat: spara detta datum ({påminnelse_datum}) i din kalender")

        st.markdown("---")

# Manuell inmatning & rekommendation
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
        rekommendation = f"🔎 För ett företag inom {bransch.lower()} med {anställda} anställda och {omsättning} MSEK i omsättning rekommenderas vanligtvis följande försäkringsmoment:\n"

        if bransch == "IT":
            rekommendation += "- Cyberförsäkring (5–15% av omsättningen)\n- Konsultansvar (2–10 MSEK)\n- Egendomsskydd för IT-utrustning"
        elif bransch == "Tillverkning":
            rekommendation += "- Egendomsförsäkring för maskiner/lager\n- Produktansvar (minst 10 MSEK)\n- Avbrottsförsäkring (upp till 12 månaders täckning)"
        elif bransch == "Transport":
            rekommendation += "- Transportöransvar & varuförsäkring\n- Trafik/vagnskada på fordon\n- Avbrott & ansvar utanför CMR"
        elif bransch == "Konsult":
            rekommendation += "- Konsultansvar (minst 2–5 MSEK)\n- Rättsskydd\n- Cyber om kunddata hanteras"
        elif bransch == "Handel":
            rekommendation += "- Lager/inventarieförsäkring\n- Produktansvar (säljled)\n- Avbrott & transport"
        elif bransch == "Bygg":
            rekommendation += "- Entreprenad/allrisk\n- ROT-ansvar\n- Egendom/maskiner + ansvarsförsäkring"
        elif bransch == "Vård":
            rekommendation += "- Patientförsäkring (lagkrav)\n- Avbrott & egendom\n- Ansvar utöver patientskadelagen"

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
