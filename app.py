import streamlit as st
import pandas as pd
import json
import re
from io import BytesIO
from docx import Document
from PyPDF2 import PdfReader
from datetime import date, timedelta

# === Funktioner ===

def to_number(varde):
    try:
        if varde is None:
            return 0
        if isinstance(varde, (int, float)):
            return int(varde)
        s = str(varde).lower()
        s = s.replace(" ", "").replace("kr", "").replace("sek", "")
        s = s.replace(",", ".")  # Hantera t.ex. 1,5m som 1.5m

        # Hantera miljoner och tusental (MSEK, m, k)
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

def extrahera_forsakringsgivare(text):
    match = re.search(r"(if|lf|trygg-hansa|moderna|protector|svedea|folksam|gjensidige|dina|lanförsäkringar)", text, re.IGNORECASE)
    if match:
        return match.group(1).capitalize()
    return "Okänt"

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

def formattera_pdf_text(text):
    text = re.sub(r"(?<=\w)\n(?=\w)", " ", text)  # Ta bort hårda radbrytningar mitt i meningar
    stycken = re.split(r"\n{2,}|(?=\n[A-ZÄÖÅ])", text)  # Dela i stycken baserat på dubbla radbrytningar eller rubriker
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

# === Visning i gränssnitt ===

if __name__ == "__main__":
    st.set_page_config(page_title="Försäkringsguide", layout="centered")
    st.title("🛡️ Försäkringsguide och Jämförelse")

    menu = st.sidebar.radio("Navigera", ["🔍 Automatisk analys", "✍️ Manuell inmatning & rekommendation"])

    if menu == "🔍 Automatisk analys":
        uploaded_pdfs = st.file_uploader("📄 Ladda upp en eller flera PDF:er", type="pdf", accept_multiple_files=True)
        påminnelse_datum = st.date_input("🔔 Vill du få en påminnelse innan förnyelse?", value=date.today() + timedelta(days=300), key="reminder_date")

        if uploaded_pdfs:
            villkorslista = []
            for i, uploaded_pdf in enumerate(uploaded_pdfs):
                reader = PdfReader(uploaded_pdf)
                full_text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"

                st.subheader(f"🔎 PDF {i+1}: {uploaded_pdf.name}")
                st.text_area("📄 PDF-innehåll (formaterat)", value=formattera_pdf_text(full_text)[:3000], height=300)

                st.subheader("📋 Extraherade värden")
                resultat = extrahera_villkor_ur_pdf(full_text)
                st.json(resultat)

                villkorslista.append(resultat)

            # Jämförelse med poängsättning
            if villkorslista:
                df = pd.DataFrame(poangsatt_villkor(villkorslista))
                st.dataframe(df.style.background_gradient(subset=["Totalpoäng"], cmap="RdYlGn"))

                st.subheader("📉 Benchmarking")
                st.markdown(f"**Snittpremie:** {df['Premie'].mean():,.0f} kr  |  **Snittsjälvrisk:** {df['Självrisk'].mean():,.0f} kr  |  **Snittpoäng:** {df['Totalpoäng'].mean():.2f}")

                st.download_button("⬇️ Ladda ner sammanställning (Word)", data=generera_word_dokument(df.to_dict(orient="records")), file_name="jamforelse_upphandling.docx")

                st.success(f"🔔 Påminnelse noterat: spara detta datum ({påminnelse_datum}) i din kalender")

        else:
            st.markdown("*Inga sparade ännu.*")

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

            # Lägg till specifika rekommendationer baserat på bransch
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
