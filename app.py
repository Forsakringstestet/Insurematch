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
        s = str(varde).replace(" ", "").replace("kr", "").replace("SEK", "").replace("k", "000").replace("MSEK", "000000")
        digits = ''.join(filter(str.isdigit, s))
        return int(digits) if digits else 0
    except Exception as e:
        st.warning(f"⚠️ Fel vid konvertering till nummer: {varde} ({type(varde).__name__}) → {e}")
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
        page_text = page.extract_text()
        if page_text:
            text += page_text + "
"
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


def poangsatt_villkor(lista):
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

    max_täckning = max(f["egendom"] + f["ansvar"] for f in normaliserade)
    max_självrisk = max(f["självrisk"] for f in normaliserade)
    max_premie = max(f["premie"] for f in normaliserade)

    resultat = []
    for f in normaliserade:
        poäng_täckning = (f["egendom"] + f["ansvar"]) / max_täckning if max_täckning else 0
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
    uploaded_pdfs = st.file_uploader(
    "📄 Ladda upp en eller flera PDF:er", key="upload_pdfs", type="pdf", accept_multiple_files=True)
    påminnelse_datum = st.date_input(
    "🔔 Vill du få en påminnelse innan förnyelse?", value=date.today() + timedelta(days=300), key="reminder_date")

    if uploaded_pdfs:
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
            st.session_state.historik.append(villkorslista)
            st.subheader("📊 Jämförelse med poängsättning")

            st.dataframe(df.style.applymap(färgschema, subset=["Totalpoäng"]))

            st.markdown("### 📉 Benchmarking")
            st.markdown(f"**Snittpremie:** {df['Premie'].mean():,.0f} kr  |  **Snittsjälvrisk:** {df['Självrisk'].mean():,.0f} kr  |  **Snittpoäng:** {df['Totalpoäng'].mean():.2f}")

            st.download_button("⬇️ Ladda ner sammanställning (Word)", data=generera_word_dokument(df.to_dict(orient="records")), file_name="jamforelse_upphandling.docx")

            st.success(f"🔔 Påminnelse noterat: spara detta datum ({påminnelse_datum}) i din kalender")

            st.markdown("---")
            st.markdown("📤 Vill du skicka detta till en mäklare? Använd nedladdningsknappen ovan och bifoga i mail.")
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
            st.session_state.historik.append(villkorslista)
            st.subheader("📊 Jämförelse med poängsättning")

            def färgschema(val):
                if isinstance(val, (int, float)):
                    if val >= 0.85:
                        return 'background-color: #b6fcb6'
                    elif val >= 0.6:
                        return 'background-color: #fff6b0'
                    else:
                        return 'background-color: #fdd'
                return ''

            st.dataframe(df.style.applymap(färgschema, subset=["Totalpoäng"]))

            st.markdown("### 📉 Benchmarking")
            st.markdown(f"**Snittpremie:** {df['Premie'].mean():,.0f} kr  |  **Snittsjälvrisk:** {df['Självrisk'].mean():,.0f} kr  |  **Snittpoäng:** {df['Totalpoäng'].mean():.2f}")

            st.download_button("⬇️ Ladda ner sammanställning (Word)", data=generera_word_dokument(df.to_dict(orient="records")), file_name="jamforelse_upphandling.docx")

            st.success(f"🔔 Påminnelse noterat: spara detta datum ({påminnelse_datum}) i din kalender")

            st.markdown("---")
            st.markdown("📤 Vill du skicka detta till en mäklare? Använd nedladdningsknappen ovan och bifoga i mail.")
