import streamlit as st
import pandas as pd
import re
from io import BytesIO
from docx import Document
from PyPDF2 import PdfReader
from datetime import date, timedelta

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
    except Exception:
        return 0

def extrahera_belopp_flex(text, keyword):
    pattern = rf"{keyword}[^0-9]*([\d\s.,]+(?:kr|sek|k|m|basbelopp)?)"
    matches = re.findall(pattern, text, re.IGNORECASE)
    numbers = [to_number(m) for m in matches]
    return max(numbers) if numbers else 0

def extrahera_forsakringsgivare(text):
    match = re.search(r"(if|lf|trygg-hansa|moderna|protector|svedea|folksam|gjensidige|dina|lanförsäkringar)", text, re.IGNORECASE)
    return match.group(1).capitalize() if match else "Okänt"

def extrahera_lista(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""

def läs_pdf_text(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        content = page.extract_text()
        if content:
            text += content + "\n"
    return text

def extrahera_premie(text):
    patterns = [
        r"bruttopremie[:\s]*([\d\s]+) ?kr",
        r"nettopremie[:\s]*([\d\s]+) ?kr",
        r"pris per år[:\s]*([\d\s]+) ?kr",
        r"premie[:\s]*([\d\s]+) ?kr",
        r"total kostnad[:\s]*([\d\s]+) ?kr",
        r"pris[:\s]*([\d\s]+) ?kr"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(" ", ""))
    return 0

def extrahera_villkor_ur_pdf(text):
    return {
        "försäkringsgivare": extrahera_forsakringsgivare(text),
        "egendom": extrahera_belopp_flex(text, "maskiner|inventarier|byggnad|fastighet|egendom"),
        "ansvar": extrahera_belopp_flex(text, "ansvar|ansvarsförsäkring|produktansvar"),
        "avbrott": extrahera_belopp_flex(text, "avbrott|förlust av täckningsbidrag|omsättning"),
        "självrisk": extrahera_belopp_flex(text, "självrisk"),
        "undantag": extrahera_lista(text, r"(undantag|exkluderat).*?:\s*(.*?)(\n|$)"),
        "premie": extrahera_premie(text),
        "villkorsreferens": "PDF"
    }
def generera_rekommendationer(bransch, data):
    rekommendationer = []

    ansvar = to_number(data.get("ansvar", 0))
    egendom = to_number(data.get("egendom", 0))
    avbrott = to_number(data.get("avbrott", 0))
    premie = to_number(data.get("premie", 0))

    if bransch == "it":
        if ansvar < 5_000_000:
            rekommendationer.append("🔍 Ansvarsförsäkring bör täcka minst 5–10 Mkr för IT-fel – överväg höjning.")
        if "cyber" not in data.get("undantag", "").lower():
            rekommendationer.append("💻 Ingen cyberförsäkring hittades – viktigt skydd vid dataintrång och driftstopp.")
        if egendom < 100_000:
            rekommendationer.append("🖥️ Egendomsförsäkring verkar låg – kontrollera värdet.")

    elif bransch == "industri":
        if ansvar < 10_000_000:
            rekommendationer.append("🏭 Ansvarsförsäkring bör vara minst 10 Mkr.")
        if avbrott < 0.1 * premie:
            rekommendationer.append("📉 Avbrottsförsäkring verkar låg i förhållande till premie.")
        if egendom < 1_000_000:
            rekommendationer.append("🏗️ Kontrollera att egendom är fullvärdesförsäkrad.")

    elif bransch == "transport":
        if ansvar < 5_000_000:
            rekommendationer.append("🚚 Ansvar bör täcka minst 5 Mkr vid skador under transport.")
        if avbrott == 0:
            rekommendationer.append("⛔ Ingen avbrottsförsäkring hittad – viktigt vid driftsavbrott.")

    elif bransch == "konsult":
        if ansvar < 2_000_000:
            rekommendationer.append("🧑‍💼 Konsultansvar bör vara minst 2 Mkr.")
        if "rättsskydd" not in data.get("undantag", "").lower():
            rekommendationer.append("⚖️ Saknar spår av rättsskydd – viktigt vid tvister.")

    elif bransch == "bygg":
        if ansvar < 10_000_000:
            rekommendationer.append("🏗️ ABT06 kräver normalt ansvar >10 Mkr.")
        if egendom < 500_000:
            rekommendationer.append("🔧 Egendom verkar låg – kontrollera verktyg och maskiner.")

    elif bransch == "handel":
        if egendom < 500_000:
            rekommendationer.append("🏬 Egendomsskydd verkar lågt – lager? inventarier?")
        if avbrott == 0:
            rekommendationer.append("⚠️ Avbrottsskydd verkar saknas – kritiskt vid brand/stöld.")

    elif bransch == "vård":
        if ansvar < 10_000_000:
            rekommendationer.append("💉 Vårdansvarsförsäkring verkar låg (<10 Mkr).")
        if "patient" not in data.get("villkorsreferens", "").lower():
            rekommendationer.append("❗ Patientförsäkring saknas i text – krävs enligt lag.")

    return rekommendationer if rekommendationer else ["✅ Försäkringsskyddet verkar tillfredsställande."]

def poangsatt_villkor(villkor_list):
    df = pd.DataFrame(villkor_list)

    df["Premie"] = df["premie"]
    df["Självrisk"] = df["självrisk"]
    df["Egendom"] = df["egendom"]
    df["Ansvar"] = df["ansvar"]
    df["Avbrott"] = df["avbrott"]

    df["Premie_poäng"] = 1 / (df["Premie"] + 1)
    df["Självrisk_poäng"] = 1 / (df["Självrisk"] + 1)
    df["Egendom_poäng"] = df["Egendom"]
    df["Ansvar_poäng"] = df["Ansvar"]
    df["Avbrott_poäng"] = df["Avbrott"]

    for col in ["Premie_poäng", "Självrisk_poäng", "Egendom_poäng", "Ansvar_poäng", "Avbrott_poäng"]:
        max_val = df[col].max()
        df[col] = df[col] / max_val * 10 if max_val > 0 else 0

    df["Totalpoäng"] = (
        df["Premie_poäng"] * 0.2 +
        df["Självrisk_poäng"] * 0.2 +
        df["Egendom_poäng"] * 0.2 +
        df["Ansvar_poäng"] * 0.2 +
        df["Avbrott_poäng"] * 0.2
    ).round(2)

    df.rename(columns={
        "försäkringsgivare": "Försäkringsgivare",
        "undantag": "Undantag",
        "villkorsreferens": "Källa"
    }, inplace=True)

    return df[[
        "Försäkringsgivare", "Premie", "Självrisk", "Egendom", "Ansvar", "Avbrott", "Undantag", "Källa", "Totalpoäng"
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
# === HUVUDAPP ===
if __name__ == "__main__":
    st.set_page_config(page_title="Försäkringsguide", page_icon="🛡️", layout="centered")
    st.title("🛡️ Försäkringsguide och Jämförelse")

    uploaded_pdfs = st.file_uploader("Ladda upp en eller flera PDF:er", type="pdf", accept_multiple_files=True)
    påminnelse_datum = st.date_input("🔔 Vill du få en påminnelse innan förnyelse?", value=date.today() + timedelta(days=300))

    if uploaded_pdfs:
        vald_bransch = st.selectbox("📂 Välj bransch för rekommendationer", [
            "it", "industri", "transport", "konsult", "handel", "bygg", "vård"
        ], index=0)

        villkorslista = []
        st.markdown("### 📂 Tidigare jämförelser:")

        for i, pdf in enumerate(uploaded_pdfs):
            text = läs_pdf_text(pdf)
            st.markdown(f"#### 📄 Fil {i+1}: {pdf.name}")
            st.text_area(f"Innehåll ur {pdf.name}", value=text[:2000], height=200)

            extrakt = extrahera_villkor_ur_pdf(text)
            villkorslista.append(extrakt)

            st.json(extrakt)

            rekommendationer = generera_rekommendationer(vald_bransch, extrakt)
            with st.expander("💡 Rekommenderade förbättringar"):
                for r in rekommendationer:
                    st.markdown(f"- {r}")

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

            st.download_button(
                "⬇️ Ladda ner sammanställning (Word)",
                data=generera_word_dokument(df.to_dict(orient="records")),
                file_name="jamforelse_upphandling.docx"
            )

            st.success(f"🔔 Påminnelse noterat: spara detta datum ({påminnelse_datum}) i din kalender")
