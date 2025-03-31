import streamlit as st
import pandas as pd
import re
import json
import pdfplumber
from PyPDF2 import PdfReader
from docx import Document
from io import BytesIO
from datetime import date, timedelta

BASBELOPP_2025 = 58800

def to_number(varde):
    try:
        if varde is None:
            return 0
        if isinstance(varde, (int, float)):
            return int(varde)
        s = str(varde).lower()
        s = s.replace(" ", "").replace(",", ".").replace("sek", "").replace("kr", "")
        if "basbelopp" in s or "bb" in s:
            val = float(re.findall(r"(\d+\.?\d*)", s)[0])
            return int(val * BASBELOPP_2025)
        if "msek" in s or "miljoner" in s:
            val = float(re.findall(r"(\d+\.?\d*)", s)[0])
            return int(val * 1_000_000)
        if "k" in s:
            val = float(re.findall(r"(\d+\.?\d*)", s)[0])
            return int(val * 1_000)
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
        return "\n".join([page.extract_text() or "" for page in reader.pages if page.extract_text()])
def extrahera_villkor_ur_pdf(text):
    def get_field(*patterns, default=0, group=1, is_number=True):
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = match.group(group)
                return to_number(val) if is_number else val
        return default

    data = {
        "försäkringsgivare": get_field(r"(försäkringsgivare|bolag)[\s:\-]+(\w+)", is_number=False),
        "försäkringsnummer": get_field(r"försäkringsnummer[\s:\-]+(\S+)", r"gäller försäkringsnummer (\S+)", is_number=False),
        "försäkringstid": get_field(r"(\d{4}-\d{2}-\d{2})\s*[-–]\s*(\d{4}-\d{2}-\d{2})", group=0, is_number=False),
        "karens": get_field(r"karens[\s:\-]+(\d+\s*(dag|dygn|dagar))", is_number=False),
        "ansvarstid": get_field(r"ansvarstid[\s:\-]+(\d+\s*(månader|år))", is_number=False),

        "premie": get_field(
            r"(nettopremie|bruttopremie|premie|kostnad|totalpris)[\s:\-]+(\d[\d\s]*\d)",
            r"totalt[\s:\-]+(\d[\d\s]*\d)"
        ),
        "självrisk": get_field(r"självrisk[\s:\-]+(\d[\d\s]*\d)", r"självrisker[\s:\-]+(\d[\d\s]*\d)"),

        "egendom_byggnad": get_field(r"(byggnad|fastighet|lokal)[\s:\-]+(\d[\d\s]*\d)", group=2),
        "egendom_maskiner": get_field(r"(maskiner|inventarier)[\s:\-]+(\d[\d\s]*\d)", group=2),
        "egendom_varor": get_field(r"(varor|lager)[\s:\-]+(\d[\d\s]*\d)", group=2),

        "ansvar_produkt": get_field(r"produktansvar[\s:\-]+(\d[\d\s]*\d)"),
        "ansvar_allmänt": get_field(r"(verksamhetsansvar|allmänt ansvar)[\s:\-]+(\d[\d\s]*\d)"),

        "avbrott_täckningsbidrag": get_field(r"täckningsbidrag[\s:\-]+(\d[\d\s]*\d)"),
        "avbrott_intäktsbortfall": get_field(r"(intäktsbortfall|förlorad omsättning)[\s:\-]+(\d[\d\s]*\d)"),

        "undantag": "",
        "villkorsreferens": "PDF"
    }

    data["försäkringsbelopp_egendom"] = sum([
        to_number(data["egendom_byggnad"]),
        to_number(data["egendom_maskiner"]),
        to_number(data["egendom_varor"])
    ])
    data["försäkringsbelopp_ansvar"] = sum([
        to_number(data["ansvar_produkt"]),
        to_number(data["ansvar_allmänt"])
    ])
    data["försäkringsbelopp_avbrott"] = sum([
        to_number(data["avbrott_täckningsbidrag"]),
        to_number(data["avbrott_intäktsbortfall"])
    ])
    return data
st.set_page_config(page_title="Försäkringsjämförelse", page_icon="🛡️", layout="centered")
st.title("🛡️ Försäkringsguide & Jämförelse")

uploaded_pdfs = st.file_uploader("📂 Ladda upp PDF:er", type="pdf", accept_multiple_files=True)
påminnelse_datum = st.date_input("🔔 Påminnelse om förnyelse", value=date.today() + timedelta(days=300))

if uploaded_pdfs:
    visa_text = st.checkbox("📄 Visa PDF-text", value=False)
    villkorslista = []

    for i, pdf in enumerate(uploaded_pdfs):
        text = läs_pdf_text(pdf)
        st.markdown(f"### 📄 Fil {i+1}: {pdf.name}")

        if visa_text:
            st.text_area("PDF-innehåll", value=text[:3000], height=250)

        extrakt = extrahera_villkor_ur_pdf(text)
        villkorslista.append(extrakt)
        st.json({k: v for k, v in extrakt.items() if isinstance(v, (str, int, float))})

        with st.expander("📁 Visa delbelopp"):
            st.markdown("#### Egendom")
            st.markdown(f"- 🏗️ Byggnad: `{to_number(extrakt['egendom_byggnad']):,} kr`")
            st.markdown(f"- 🧰 Maskiner: `{to_number(extrakt['egendom_maskiner']):,} kr`")
            st.markdown(f"- 📦 Varor: `{to_number(extrakt['egendom_varor']):,} kr`")

            st.markdown("#### Ansvar")
            st.markdown(f"- 📜 Allmänt: `{to_number(extrakt['ansvar_allmänt']):,} kr`")
            st.markdown(f"- ⚖️ Produktansvar: `{to_number(extrakt['ansvar_produkt']):,} kr`")

            st.markdown("#### Avbrott")
            st.markdown(f"- 💸 Täckningsbidrag: `{to_number(extrakt['avbrott_täckningsbidrag']):,} kr`")
            st.markdown(f"- 📉 Intäktsbortfall: `{to_number(extrakt['avbrott_intäktsbortfall']):,} kr`")

        saknade = [k for k in ["premie", "självrisk", "försäkringsbelopp_egendom", "försäkringsbelopp_ansvar"]
                   if to_number(extrakt.get(k)) == 0]
        if saknade:
            st.warning(f"⚠️ Saknade värden i {pdf.name}: {', '.join(saknade)}")

        st.markdown("---")
def färgschema(value):
    if value >= 8:
        return 'background-color: #c4f5c2'
    elif value >= 6:
        return 'background-color: #fff4a3'
    elif value >= 4:
        return 'background-color: #ffd2a3'
    else:
        return 'background-color: #ffb6b6'

def poangsatt_villkor(lista):
    df = pd.DataFrame(lista)

    df["Premie"] = df["premie"].apply(to_number)
    df["Självrisk"] = df["självrisk"].apply(to_number)
    df["Egendom"] = df["försäkringsbelopp_egendom"]
    df["Ansvar"] = df["försäkringsbelopp_ansvar"]
    df["Avbrott"] = df["försäkringsbelopp_avbrott"]

    max_premie = df["Premie"].max()
    max_självrisk = df["Självrisk"].max()
    max_egendom = df["Egendom"].max()
    max_ansvar = df["Ansvar"].max()
    max_avbrott = df["Avbrott"].max()

    def maxify(v, m): return round((v / m * 10) if m > 0 else 0, 2)
    def minify(v, m): return round((1 - v / m) * 10 if m > 0 else 0, 2)

    df["Poäng_premie"] = df["Premie"].apply(lambda x: minify(x, max_premie))
    df["Poäng_självrisk"] = df["Självrisk"].apply(lambda x: minify(x, max_självrisk))
    df["Poäng_egendom"] = df["Egendom"].apply(lambda x: maxify(x, max_egendom))
    df["Poäng_ansvar"] = df["Ansvar"].apply(lambda x: maxify(x, max_ansvar))
    df["Poäng_avbrott"] = df["Avbrott"].apply(lambda x: maxify(x, max_avbrott))

    df["Totalpoäng"] = df[[
        "Poäng_premie", "Poäng_självrisk", "Poäng_egendom", "Poäng_ansvar", "Poäng_avbrott"
    ]].mean(axis=1).round(2)

    return df[[
        "försäkringsgivare", "Premie", "Självrisk", "Egendom", "Ansvar", "Avbrott",
        "försäkringstid", "försäkringsnummer", "karens", "ansvarstid", "undantag", "villkorsreferens", "Totalpoäng"
    ]]
def generera_word_dokument(data):
    doc = Document()
    doc.add_heading("Upphandlingsunderlag – Försäkringsjämförelse", level=1)
    table = doc.add_table(rows=1, cols=len(data[0]))
    hdr_cells = table.rows[0].cells
    for i, key in enumerate(data[0].keys()):
        hdr_cells[i].text = key
    for row in data:
        row_cells = table.add_row().cells
        for i, key in enumerate(row):
            row_cells[i].text = str(row[key])
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def generera_json(data):
    buffer = BytesIO()
    buffer.write(json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))
    buffer.seek(0)
    return buffer

# 📊 GUI: Sammanställning & benchmarking
if uploaded_pdfs and villkorslista:
    df = poangsatt_villkor(villkorslista)
    st.subheader("📊 Sammanställning & poängsättning")
    st.dataframe(df.style.applymap(färgschema, subset=["Totalpoäng"]))

    st.subheader("📉 Benchmarking")
    st.markdown(f"""
        **Snittpremie:** {df['Premie'].mean():,.0f} kr  
        **Snittsjälvrisk:** {df['Självrisk'].mean():,.0f} kr  
        **Snittpoäng:** {df['Totalpoäng'].mean():.2f}
    """)

    st.download_button("⬇️ Ladda ner sammanställning (Word)",
        data=generera_word_dokument(df.to_dict(orient="records")),
        file_name="jamforelse_upphandling.docx"
    )
    st.download_button("⬇️ Exportera som JSON",
        data=generera_json(villkorslista),
        file_name="jamforelse_data.json"
    )

    st.success(f"🔔 Påminnelse: Lägg in {påminnelse_datum} i din kalender 📅")
