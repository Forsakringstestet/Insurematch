import streamlit as st
import pandas as pd
import re
from io import BytesIO
from docx import Document
from PyPDF2 import PdfReader
from datetime import date, timedelta

# === Funktioner ===

# Funktion för att konvertera text till nummer (försäkringsbelopp etc.)
def to_number(varde):
    try:
        if varde is None:
            return 0
        if isinstance(varde, (int, float)):
            return int(varde)
        s = str(varde).lower()
        s = s.replace(" ", "").replace("kr", "").replace("sek", "")
        s = s.replace(",", ".")  # hantera t.ex. 1,5m som 1.5m
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

# Funktion för att extrahera belopp från text (t.ex. PDF)
def extrahera_belopp(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return "0"

# Funktion för att extrahera försäkringsbolag från PDF
def extrahera_forsakringsgivare(text):
    match = re.search(r"(if|lf|trygg-hansa|moderna|protector|svedea|folksam|gjensidige|dina|lanförsäkringar)", text, re.IGNORECASE)
    if match:
        return match.group(1).capitalize()
    return "Okänt"

# Funktion för att extrahera villkor från PDF
def extrahera_villkor_ur_pdf(text):
    return {
        "försäkringsgivare": extrahera_forsakringsgivare(text),
        "egendom": extrahera_belopp(text, r"(egendom|byggnad|fastighet).*?(\d+[\s]*[MmKkMmSEKsek,\.]*[\s]*SEK|kr)"),
        "ansvar": extrahera_belopp(text, r"(ansvar|skadestånd).*?(\d+[\s]*[MmKkMmSEKsek,\.]*[\s]*SEK|kr)"),
        "avbrott": extrahera_belopp(text, r"(avbrott|förlust av intäkt|driftstopp).*?(\d+[\s]*[MmKkMmSEKsek,\.]*[\s]*SEK|kr)"),
        "självrisk": extrahera_belopp(text, r"(självrisk|självrisken).*?(\d+[\s]*[MmKkMmSEKsek,\.]*[\s]*SEK|kr)"),
        "undantag": extrahera_belopp(text, r"(undantag|exkluderat).*?:\s*(.*?)(\n|$)"),
        "premie": extrahera_belopp(text, r"(premie|försäkringsbelopp).*?(\d+[\s]*[MmKkMmSEKsek,\.]*[\s]*SEK|kr)"),
        "villkorsreferens": "PDF"
    }

# Funktion för att läsa in PDF-text
def läs_pdf_text(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

# Funktion för att skapa en Word-rapport från sammanställd data
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

# Funktion för att jämföra och poängsätta villkor
def poangsatt_villkor(lista):
    normaliserade = []
    for rad in lista:
        normaliserade.append({
            "Bolag": rad.get("försäkringsgivare", "Okänt"),
            "Egendom": to_number(rad.get("egendom")),
            "Ansvar": to_number(rad.get("ansvar")),
            "Avbrott": to_number(rad.get("avbrott")),
            "Självrisk": to_number(rad.get("självrisk")),
            "Premie": to_number(rad.get("premie")),
            "Undantag": rad.get("undantag", "")
        })

    max_täckning = max((f["Egendom"] + f["Ansvar"]) for f in normaliserade) or 1
    max_självrisk = max((f["Självrisk"] for f in normaliserade)) or 1
    max_premie = max((f["Premie"] for f in normaliserade)) or 1

    resultat = []
    for f in normaliserade:
        poäng_täckning = (f["Egendom"] + f["Ansvar"]) / max_täckning
        poäng_självrisk = 1 - (f["Självrisk"] / max_självrisk)
        poäng_premie = 1 - (f["Premie"] / max_premie)
        totalpoäng = round(0.5 * poäng_täckning + 0.2 * poäng_självrisk + 0.3 * poäng_premie, 3)
        f["Totalpoäng"] = totalpoäng
        resultat.append(f)

    return sorted(resultat, key=lambda x: x["Totalpoäng"], reverse=True)

# === Streamlit gränssnitt ===

st.set_page_config(page_title="Försäkringsguide", page_icon="🛡️", layout="centered")
st.title("🛡️ Försäkringsguide och Jämförelse")

menu = st.sidebar.radio("Navigera", ["🔍 Automatisk analys", "✍️ Manuell inmatning & rekommendation"])

if menu == "🔍 Automatisk analys":
    uploaded_pdfs = st.file_uploader("📄 Ladda upp en eller flera PDF:er", type="pdf", accept_multiple_files=True)
    if uploaded_pdfs:
        villkorslista = []
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
            st.dataframe(df)

            st.download_button("⬇️ Ladda ner sammanställning (Word)", data=generera_word_dokument(df.to_dict(orient="records")), file_name="jamforelse_upphandling.docx")
            st.success(f"✅ Jämförelse klar!")

elif menu == "✍️ Manuell inmatning & rekommendation":
    with st.form("företagsformulär"):
        företagsnamn = st.text_input("Företagsnamn")
        omsättning = st.number_input("Omsättning (MSEK)", min_value=0.0, step=0.1)
        anställda = st.number_input("Antal anställda", min_value=0, step=1)
        bransch = st.selectbox("Bransch", ["IT", "Tillverkning", "Transport", "Konsult", "Handel", "Bygg", "Vård"])
        ort = st.text_input("Stad")
        land = st.text_input("Land", value="Sverige")
        nuvarande_forsakring = st.text_input("Nuvarande försäkringsbolag (valfritt)")

        egendom = st.number_input("Egendomsvärde (kr)", step=10000)
        ansvar = st.number_input("Ansvarsskydd (kr)", step=10000)
        avbrott = st.number_input("Avbrottsersättning (kr)", step=10000)
        premie = st.number_input("Premie per år (kr)", step=10000)
        
        submitted = st.form_submit_button("Analysera")

    if submitted:
        st.success(f"🎯 Analys för {företagsnamn} inom {bransch}!")
        rekommendation = f"För {bransch} med {anställda} anställda och {omsättning} MSEK i omsättning rekommenderas: \n"

        # Lägg till rekommendation baserat på bransch
        if bransch == "IT":
            rekommendation += "- Cyberförsäkring\n- Konsultansvar\n- Egendomsskydd"
        
        st.markdown(f"### 📌 Rekommenderat försäkringsupplägg\n{rekommendation}")
        st.download_button("⬇️ Exportera rekommendation", data=generera_word_dokument([{
            "Företag": företagsnamn,
            "Org.nr": "Ej angivet",
            "Bransch": bransch,
            "Egendom": egendom,
            "Ansvar": ansvar,
            "Avbrott": avbrott,
            "Premie": premie,
            "Ort": ort,
            "Land": land,
            "Rekommendation": rekommendation
        }]), file_name="forsakringsrekommendation.docx")
