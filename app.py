import streamlit as st
import pandas as pd
import re
import json
import pdfplumber
from io import BytesIO
from docx import Document
from PyPDF2 import PdfReader
from datetime import date, timedelta

# Basbelopp för 2025
BASBELOPP_2025 = 58800
def to_number(varde):
    try:
        if varde is None:
            return 0
        if isinstance(varde, (int, float)):
            return int(varde)
        s = str(varde).lower()
        s = s.replace(" ", "").replace("kr", "").replace("sek", "").replace(",", ".")
        if "basbelopp" in s:
            val = float(re.findall(r"(\d+\.?\d*)", s)[0])
            return int(val * BASBELOPP_2025)
        elif "msek" in s:
            return int(float(s.replace("msek", "")) * 1_000_000)
        elif "m" in s:
            return int(float(s.replace("m", "")) * 1_000_000)
        elif "k" in s:
            return int(float(s.replace("k", "")) * 1_000)
        digits = ''.join(filter(lambda x: x.isdigit() or x == '.', s))
        return int(float(digits)) if digits else 0
    except:
        return 0

def läs_pdf_text(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            return "\n".join([page.extract_text() or "" for page in pdf.pages])
    except:
        reader = PdfReader(pdf_file)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
def extrahera_premie(text):
    patterns = [
        r"bruttopremie[:\s]*([\d\s]+) ?kr",
        r"nettopremie[:\s]*([\d\s]+) ?kr",
        r"pris per år[:\s]*([\d\s]+)",
        r"premie[:\s]*([\d\s]+) ?kr",
        r"total kostnad[:\s]*([\d\s]+)",
        r"pris[:\s]*([\d\s]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                value = match.group(1).replace(" ", "")
                return int(value)
            except:
                continue
    return 0

def extrahera_forsakringsgivare(text):
    match = re.search(r"(if|lf|trygg-hansa|moderna|protector|svedea|folksam|gjensidige|dina|lanförsäkringar)", text, re.IGNORECASE)
    return match.group(1).capitalize() if match else "Okänt"

def extrahera_lista(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""
def extrahera_villkor_ur_pdf(text):
    def hitta_summa(text, nyckelord, matcha_flera=False):
        mönster = rf"{nyckelord}[^0-9]*([\d\s.,]+)( kr| sek|:-)?"
        belopp = re.findall(mönster, text, re.IGNORECASE)
        summor = [to_number(match[0]) for match in belopp]
        return sum(summor) if (matcha_flera and summor) else (max(summor) if summor else 0)

    def extrahera_datumperiod(text):
        match = re.search(r"(\d{4}-\d{2}-\d{2})\s*(–|-|till)\s*(\d{4}-\d{2}-\d{2})", text)
        return f"{match.group(1)} – {match.group(3)}" if match else ""

    def extrahera_forsakringsnummer(text):
        match = re.search(r"(försäkringsnummer|avtalsnummer)[\s:]*([A-Z0-9\-]+)", text, re.IGNORECASE)
        return match.group(2).strip() if match else ""

    def extrahera_lank(text):
        match = re.search(r"https?://[^\s]+", text)
        return match.group(0) if match else "PDF"

    return {
        "försäkringsgivare": extrahera_forsakringsgivare(text),
        "egendom": hitta_summa(text, r"(egendom|byggnad|fastighet|maskiner|inventarier)", matcha_flera=True),
        "ansvar": hitta_summa(text, r"(ansvar|ansvarsförsäkring|produktansvar|verksamhetsansvar)", matcha_flera=True),
        "avbrott": hitta_summa(text, r"(avbrott|förlust av täckningsbidrag|intäktsbortfall|omsättning)", matcha_flera=True),
        "självrisk": hitta_summa(text, r"(självrisk|självrisken|grundsjälvrisk)"),
        "undantag": extrahera_lista(text, r"(undantag|exkluderat).*?:\s*(.*?)(\n|$)"),
        "premie": extrahera_premie(text),
        "försäkringstid": extrahera_datumperiod(text),
        "försäkringsnummer": extrahera_forsakringsnummer(text),
        "villkorsreferens": extrahera_lank(text)
    }
def generera_rekommendationer(bransch, data):
    rekommendationer = []
    ansvar = to_number(data.get("ansvar", 0))
    egendom = to_number(data.get("egendom", 0))
    avbrott = to_number(data.get("avbrott", 0))
    premie = to_number(data.get("premie", 0))

    if bransch == "it":
        if ansvar < 5_000_000:
            rekommendationer.append("🔍 Ansvarsförsäkring bör täcka minst 5–10 Mkr.")
        if egendom < 100_000:
            rekommendationer.append("🖥️ Egendom verkar låg – kontrollera kontorsutrustning.")
        if avbrott == 0:
            rekommendationer.append("💻 Avbrottsskydd saknas – kritiskt för IT-system.")
    elif bransch == "industri":
        if ansvar < 10_000_000:
            rekommendationer.append("🏭 Ansvarsförsäkring bör vara minst 10 Mkr.")
        if egendom < 1_000_000:
            rekommendationer.append("🏗️ Egendom verkar låg – maskiner, lokaler?")
        if avbrott < 0.1 * premie:
            rekommendationer.append("📉 Avbrottsförsäkring verkar låg i relation till premie.")
    elif bransch == "transport":
        if ansvar < 5_000_000:
            rekommendationer.append("🚛 Ansvar bör vara minst 5 Mkr.")
        if avbrott == 0:
            rekommendationer.append("📦 Avbrottsskydd saknas – viktigt vid fordonshaveri.")
    elif bransch == "konsult":
        if ansvar < 2_000_000:
            rekommendationer.append("🧠 Konsultansvar bör vara minst 2–5 Mkr.")
        if "rättsskydd" not in data.get("undantag", "").lower():
            rekommendationer.append("⚖️ Kontrollera att rättsskydd finns.")
    elif bransch == "bygg":
        if ansvar < 10_000_000:
            rekommendationer.append("🔨 ABT04/ABT06 kräver minst 10 Mkr ansvar.")
        if egendom < 500_000:
            rekommendationer.append("🛠️ Lågt skydd – maskiner, verktyg?")
    elif bransch == "handel":
        if egendom < 300_000:
            rekommendationer.append("🛒 Kontrollera lagervärde och försäkring.")
        if avbrott == 0:
            rekommendationer.append("🚫 Avbrottsskydd verkar saknas – risk vid driftstopp.")
    elif bransch == "vård":
        if ansvar < 10_000_000:
            rekommendationer.append("💉 Vårdansvar bör vara minst 10 Mkr.")
        if "patient" not in data.get("villkorsreferens", "").lower():
            rekommendationer.append("🩺 Patientförsäkring saknas eller otydlig.")

    return rekommendationer if rekommendationer else ["✅ Försäkringsskyddet verkar tillfredsställande."]

def poangsatt_villkor(villkor_list):
    df = pd.DataFrame(villkor_list)

    df["Premie"] = df["premie"].apply(to_number)
    df["Självrisk"] = df["självrisk"].apply(to_number)
    df["Egendom"] = df["egendom"].apply(to_number)
    df["Ansvar"] = df["ansvar"].apply(to_number)
    df["Avbrott"] = df["avbrott"].apply(to_number)

    df["Premie_poäng"] = 1 / (df["Premie"] + 1)
    df["Självrisk_poäng"] = 1 / (df["Självrisk"] + 1)
    df["Egendom_poäng"] = df["Egendom"]
    df["Ansvar_poäng"] = df["Ansvar"]
    df["Avbrott_poäng"] = df["Avbrott"]

    for col in ["Premie_poäng", "Självrisk_poäng", "Egendom_poäng", "Ansvar_poäng", "Avbrott_poäng"]:
        max_val = df[col].max()
        df[col] = df[col] / max_val * 10 if max_val > 0 else 0

    df["Totalpoäng"] = (
        df["Premie_poäng"] * 0.20 +
        df["Självrisk_poäng"] * 0.15 +
        df["Egendom_poäng"] * 0.25 +
        df["Ansvar_poäng"] * 0.25 +
        df["Avbrott_poäng"] * 0.15
    ).round(2)

    df.rename(columns={
        "försäkringsgivare": "Försäkringsgivare",
        "undantag": "Undantag",
        "villkorsreferens": "Källa",
        "försäkringstid": "Försäkringstid",
        "försäkringsnummer": "Försäkringsnummer"
    }, inplace=True)

    return df[[
        "Försäkringsgivare", "Premie", "Självrisk", "Egendom", "Ansvar", "Avbrott",
        "Undantag", "Försäkringstid", "Försäkringsnummer", "Källa", "Totalpoäng"
    ]]
def färgschema(value):
    if value >= 8:
        return 'background-color: #b6fcb6'
    elif value >= 6:
        return 'background-color: #f9fcb6'
    elif value >= 4:
        return 'background-color: #fde2b6'
    else:
        return 'background-color: #fcb6b6'

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

def generera_json(data):
    buffer = BytesIO()
    buffer.write(json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))
    buffer.seek(0)
    return buffer
# === HUVUDAPP ===
if __name__ == "__main__":
    st.set_page_config(page_title="Försäkringsguide", page_icon="🛡️", layout="centered")
    st.title("🛡️ Försäkringsguide & Jämförelse")

    uploaded_pdfs = st.file_uploader("📂 Ladda upp en eller flera PDF:er", type="pdf", accept_multiple_files=True)
    påminnelse_datum = st.date_input("🔔 Vill du få en påminnelse innan förnyelse?", value=date.today() + timedelta(days=300))

    if uploaded_pdfs:
        vald_bransch = st.selectbox("🏢 Välj bransch", [
            "it", "industri", "transport", "konsult", "handel", "bygg", "vård"
        ], index=0)

        visa_rådata = st.checkbox("📊 Visa extraherade rådata (per PDF)")

        villkorslista = []
        st.markdown("### 📄 Analys per offert:")

        for i, pdf in enumerate(uploaded_pdfs):
            text = läs_pdf_text(pdf)
            st.markdown(f"#### 📑 Fil {i+1}: {pdf.name}")
            st.text_area("📃 Innehåll (förhandsgranskning)", value=text[:2000], height=200)

            extrakt = extrahera_villkor_ur_pdf(text)
            villkorslista.append(extrakt)

            if visa_rådata:
                st.json(extrakt)

            rekommendationer = generera_rekommendationer(vald_bransch, extrakt)
            with st.expander("💡 Rekommenderade förbättringar"):
                for r in rekommendationer:
                    st.markdown(f"- {r}")

            saknade = [k for k, v in extrakt.items() if to_number(v) == 0 and k not in ["undantag", "villkorsreferens"]]
            if saknade:
                st.warning(f"⚠️ Saknade fält i {pdf.name}: {', '.join(saknade)}")

            st.markdown("---")

        if villkorslista:
            df = pd.DataFrame(poangsatt_villkor(villkorslista))
            df = df[[
                "Försäkringsgivare", "Premie", "Självrisk", "Egendom",
                "Ansvar", "Avbrott", "Undantag", "Försäkringstid",
                "Försäkringsnummer", "Källa", "Totalpoäng"
            ]]

            st.subheader("📊 Sammanställning & poängsättning")
            st.dataframe(df.style
                .format({
                    "Premie": "{:,.0f} kr",
                    "Självrisk": "{:,.0f} kr",
                    "Egendom": "{:,.0f} kr",
                    "Ansvar": "{:,.0f} kr",
                    "Avbrott": "{:,.0f} kr",
                    "Totalpoäng": "{:.2f}"
                })
                .applymap(färgschema, subset=["Totalpoäng"])
            )

            st.markdown("### 📉 Benchmarking")
            st.markdown(f"**Snittpremie:** {df['Premie'].mean():,.0f} kr  |  **Snittsjälvrisk:** {df['Självrisk'].mean():,.0f} kr  |  **Snittpoäng:** {df['Totalpoäng'].mean():.2f}")

            st.download_button(
                "⬇️ Ladda ner sammanställning (Word)",
                data=generera_word_dokument(df.to_dict(orient="records")),
                file_name="jamforelse_upphandling.docx"
            )

            st.download_button(
                "💾 Exportera som JSON",
                data=generera_json(villkorslista),
                file_name="jamforelse_upphandling.json"
            )

            st.success(f"🔔 Påminnelse noterat: spara detta datum ({påminnelse_datum}) i din kalender")
