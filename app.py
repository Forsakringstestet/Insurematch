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
    """
    Robust omvandling till heltal (kr).
    Hanterar None, int, float, str och loggar varning vid fel.
    """
    try:
        if varde is None:
            return 0
        if isinstance(varde, (int, float)):
            return int(varde)
        s = str(varde).replace(" ", "").replace("kr", "").replace("SEK", "").replace("k", "000").replace("MSEK", "000000")
        digits = ''.join(filter(str.isdigit, s))
        return int(digits) if digits else 0
    except Exception as e:
        st.warning(f"⚠️ Fel vid konvertering till nummer: {varde} ({type(varde).__name__}) → {e}")
        return 0

def extrahera_belopp(text, pattern):
    """
    Söker i PDF-texten efter belopp med ett visst mönster (regex).
    Returnerar '0' om ingen träff.
    """
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return "0"

def extrahera_lista(text, pattern):
    """
    Söker i PDF-texten efter en lista (t.ex. undantag).
    Returnerar tom sträng om ingen träff.
    """
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def extrahera_villkor_ur_pdf(text):
    """
    Extraherar försäkringsrelaterade fält från PDF-texten med regex.
    Returnerar en ordbok med 'egendom', 'ansvar', 'avbrott', 'självrisk', 'undantag', 'premie' m.m.
    """
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
    """
    Returnerar hela texten från en PDF.
    """
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def generera_word_dokument(data):
    """
    Skapar en Word-fil från en lista med ordböcker (data).
    Returnerar en BytesIO som kan laddas ner i Streamlit.
    """
    doc = Document()
    doc.add_heading("Upphandlingsunderlag – Försäkringsjämförelse", level=1)
    # Skapa tabell med rubriker
    table = doc.add_table(rows=1, cols=len(data[0]))
    hdr_cells = table.rows[0].cells
    for i, key in enumerate(data[0].keys()):
        hdr_cells[i].text = key
    # Fyll på tabellrader
    for row in data:
        cells = table.add_row().cells
        for i, key in enumerate(row):
            cells[i].text = str(row[key])
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def färgschema(val):
    """
    Färgkodar celler i DataFrame beroende på värde i 'Totalpoäng'.
    """
    if isinstance(val, (int, float)):
        if val >= 0.85:
            return 'background-color: #b6fcb6'  # grönt
        elif val >= 0.6:
            return 'background-color: #fff6b0'  # gult
        else:
            return 'background-color: #fdd'     # rött
    return ''

def poangsatt_villkor(lista):
    """
    Tar en lista av ordböcker med 'egendom', 'ansvar', 'självrisk', 'premie' etc.
    Beräknar poäng baserat på:
      - 0.5 * (täckning) [egendom+ansvar]
      - 0.2 * (1 - självrisk/ max_självrisk)
      - 0.3 * (1 - premie / max_premie)
    Returnerar sorterad lista med totalpoäng (högst först).
    """
    normaliserade = []
    for rad in lista:
        normaliserade.append({
            "bolag": rad.get("försäkringsgivare", "Okänt"),
            "egendom": to_number(rad.get("egendom")),
            "ansvar": to_number(rad.get("ansvar")),
            "avbrott": to_number(rad.get("avbrott")),
            "självrisk": to_number(rad.get("självrisk")),
            "premie": to_number(rad.get("premie")),
            "undantag": rad.get("undantag", "")
        })

    # Hitta maxvärden
    max_täckning = max(f["egendom"] + f["ansvar"] for f in normaliserade) if normaliserade else 1
    max_självrisk = max(f["självrisk"] for f in normaliserade) if normaliserade else 1
    max_premie = max(f["premie"] for f in normaliserade) if normaliserade else 1

    resultat = []
    for f in normaliserade:
        total_täckning = f["egendom"] + f["ansvar"]
        poäng_täckning = total_täckning / max_täckning if max_täckning else 0
        poäng_självrisk = 1 - (f["självrisk"] / max_självrisk) if max_självrisk else 0
        poäng_premie = 1 - (f["premie"] / max_premie) if max_premie else 0
        totalpoäng = round(0.5 * poäng_täckning + 0.2 * poäng_självrisk + 0.3 * poäng_premie, 3)

        resultat.append({
            "Bolag": f["bolag"],
            "Totalpoäng": totalpoäng,
            "Egendom": f["egendom"],
            "Ansvar": f["ansvar"],
            "Självrisk": f["självrisk"],
            "Premie": f["premie"],
            "Undantag": f["undantag"]
        })

    return sorted(resultat, key=lambda x: x["Totalpoäng"], reverse=True)

# === App-gränssnitt ===

st.set_page_config(page_title="Försäkringsguide", page_icon="🛡️", layout="centered")
st.title("🛡️ Försäkringsguide och Jämförelse")

menu = st.sidebar.radio("Navigera", ["🔍 Automatisk analys", "✍️ Manuell inmatning & rekommendation"])

if menu == "🔍 Automatisk analys":
    # Ladda upp flera PDF:er
    uploaded_pdfs = st.file_uploader(
        "📄 Ladda upp en eller flera PDF:er", key="upload_pdfs", type="pdf", accept_multiple_files=True
    )
    # Välj datum för påminnelse
    påminnelse_datum = st.date_input(
        "🔔 Vill du få en påminnelse innan förnyelse?", value=date.today() + timedelta(days=300), key="reminder_date"
    )

    # Om vi har laddat upp PDF:er
    if uploaded_pdfs:
        # Kolla historik
        if 'historik' not in st.session_state:
            st.session_state.historik = []

        villkorslista = []

        st.markdown("### 📂 Tidigare jämförelser (denna session):")
        if st.session_state.historik:
            if st.button("🗑️ Rensa historik"):
                st.session_state.historik = []
                st.experimental_rerun()

            for i, jämförelse in enumerate(st.session_state.historik):
                with st.expander(f"🗂️ Jämförelse {i+1} – {len(jämförelse)} bolag"):
                    df_hist = pd.DataFrame(poangsatt_villkor(jämförelse))
                    st.dataframe(df_hist.style.applymap(färgschema, subset=["Totalpoäng"]))
        else:
            st.markdown("*Inga sparade ännu.*")

        # Analysera varje PDF
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

        # När vi är klara med alla PDF:er
        if villkorslista:
            df = pd.DataFrame(poangsatt_villkor(villkorslista))
            # Spara i historik
            st.session_state.historik.append(villkorslista)

            st.subheader("📊 Jämförelse med poängsättning")
            st.dataframe(df.style.applymap(färgschema, subset=["Totalpoäng"]))

            st.markdown("### 📉 Benchmarking")
            st.markdown(
                f"**Snittpremie:** {df['Premie'].mean():,.0f} kr  |  "
                f"**Snittsjälvrisk:** {df['Självrisk'].mean():,.0f} kr  |  "
                f"**Snittpoäng:** {df['Totalpoäng'].mean():.2f}"
            )

            st.download_button(
                "⬇️ Ladda ner sammanställning (Word)",
                data=generera_word_dokument(df.to_dict(orient="records")),
                file_name="jamforelse_upphandling.docx"
            )

            st.success(f"🔔 Påminnelse noterat: spara detta datum ({påminnelse_datum}) i din kalender")

            st.markdown("---")
            st.markdown("📤 Vill du skicka detta till en mäklare? Använd nedladdningsknappen ovan och bifoga i mail.")

    else:
        # Om inga PDF:er har laddats upp
        st.info("Ingen PDF uppladdad ännu.")


elif menu == "✍️ Manuell inmatning & rekommendation":
    st.subheader("🏢 Företagsinformation")
    with st.form("företagsformulär"):
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
        rekommendation = f"🔎 För ett företag inom {bransch.lower()} med {anställda} anställda och {omsättning} MSEK i omsättning rekommenderas vanligtvis:\n\n"

        if bransch == "IT":
            rekommendation += "- Cyberförsäkring (5–15% av omsättningen)\n- Konsultansvar (2–10 MSEK)\n- Egendomsskydd"
        elif bransch == "Tillverkning":
            rekommendation += "- Egendomsförsäkring för maskiner/lager\n- Produktansvar (minst 10 MSEK)\n- Avbrottsförsäkring (upp till 12 mån)"
        elif bransch == "Transport":
            rekommendation += "- Transportöransvar & varuförsäkring\n- Trafik/vagnskada på fordon\n- Avbrott & ansvar"
        elif bransch == "Konsult":
            rekommendation += "- Konsultansvar (minst 2–5 MSEK)\n- Rättsskydd\n- Cyber om kunddata hanteras"
        elif bransch == "Handel":
            rekommendation += "- Lager/inventarieförsäkring\n- Produktansvar (säljled)\n- Avbrott & transport"
        elif bransch == "Bygg":
            rekommendation += "- Entreprenad/allrisk\n- ROT-ansvar\n- Egendom/maskiner + ansvarsförsäkring"
        elif bransch == "Vård":
            rekommendation += "- Patientförsäkring (lagkrav)\n- Avbrott & egendom\n- Ansvar utöver patientskadelagen"

        st.markdown(f"#### 📌 Rekommenderat försäkringsupplägg\n{rekommendation}")

        # Ladda ner Word-fil med företagsuppgifterna och rekommendation
        st.download_button(
            "⬇️ Exportera förslag (Word)",
            data=generera_word_dokument([{
                "Företag": företagsnamn,
                "Org.nr": orgnr,
                "Bransch": bransch,
                "Egendom": egendom,
                "Ansvar": ansvar,
                "Avbrott": avbrott,
                "Premie": premie,
                "Ort": ort,
                "Land": land,
                "Nuvarande bolag": nuvarande,
                "Rekommendation": rekommendation
            }]),
            file_name="forsakringsrekommendation.docx"
        )
