import streamlit as st
import pandas as pd
import json
import re
from io import BytesIO
from docx import Document
from PyPDF2 import PdfReader

# --- FUNKTIONER ---
def to_number(varde):
    if varde is None:
        return 0
    s = str(varde).replace(" ", "").replace("kr", "").replace("SEK", "").replace("k", "000").replace("MSEK", "000000")
    return int(''.join(filter(str.isdigit, s)))

def normalisera_data(radata):
    return {
        "bolag": radata.get("försäkringsgivare", "Okänt"),
        "egendom": to_number(radata.get("egendom", 0)),
        "ansvar": to_number(radata.get("ansvar", 0)),
        "avbrott": to_number(radata.get("avbrott", 0)),
        "självrisk": to_number(radata.get("självrisk", 0)),
        "undantag": [u.strip().lower() for u in radata.get("undantag", "").split(",")],
        "premie": to_number(radata.get("premie", 0)),
        "villkor_id": radata.get("villkorsreferens", "PDF")
    }

def jämför_försäkringar(försäkringar):
    vikt_täckning = 0.5
    vikt_självrisk = 0.2
    vikt_premie = 0.3

    max_täckning = max(f["egendom"] + f["ansvar"] for f in försäkringar)
    max_självrisk = max(f["självrisk"] for f in försäkringar)
    max_premie = max(f["premie"] for f in försäkringar)

    resultat = []

    for f in försäkringar:
        total_täckning = f["egendom"] + f["ansvar"]
        poäng_täckning = total_täckning / max_täckning
        poäng_självrisk = 1 - (f["självrisk"] / max_självrisk)
        poäng_premie = 1 - (f["premie"] / max_premie)

        totalpoäng = (
            vikt_täckning * poäng_täckning +
            vikt_självrisk * poäng_självrisk +
            vikt_premie * poäng_premie
        )

        resultat.append({
            "Bolag": f["bolag"],
            "Totalpoäng": round(totalpoäng, 3),
            "Undantag": ", ".join(f["undantag"]),
            "Premie": f["premie"],
            "Självrisk": f["självrisk"],
            "Täckning Egendom": f["egendom"],
            "Täckning Ansvar": f["ansvar"],
            "Villkor ID": f["villkor_id"]
        })

    return sorted(resultat, key=lambda x: x["Totalpoäng"], reverse=True)

def generera_word_dokument(data):
    doc = Document()
    doc.add_heading('Upphandlingsunderlag – Försäkringsjämförelse', level=1)
    doc.add_paragraph('Detta dokument genererades automatiskt via Streamlit-appen. Nedan följer en sammanställning av rankade försäkringsförslag.')

    table = doc.add_table(rows=1, cols=len(data[0]))
    table.style = 'Table Grid'
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

def läs_pdf_text(pdf_file):
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def extrahera_villkor_ur_pdf(text):
    return {
        "försäkringsgivare": "Okänt",
        "egendom": extrahera_belopp(text, r"egendom.*?(\d+[\s]*[MmKk]?SEK|kr)"),
        "ansvar": extrahera_belopp(text, r"ansvar.*?(\d+[\s]*[MmKk]?SEK|kr)"),
        "avbrott": extrahera_belopp(text, r"avbrott.*?(\d+[\s]*[MmKk]?SEK|kr)"),
        "självrisk": extrahera_belopp(text, r"självrisk.*?(\d+[\s]*[MmKk]?SEK|kr)"),
        "undantag": extrahera_lista(text, r"undantag.*?:\s*(.*)\n"),
        "premie": extrahera_belopp(text, r"premie.*?(\d+[\s]*[MmKk]?SEK|kr)"),
        "villkorsreferens": "PDF"
    }

def extrahera_belopp(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1) if match else "0"

def extrahera_lista(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

# --- GRENSSNITT ---
st.set_page_config(page_title="Försäkringsjämförelse", page_icon="🛡️", layout="centered")
st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Insurance_icon.svg/1200px-Insurance_icon.svg.png", width=80)
st.title("🛡️ Försäkringsjämförelse – Upphandling")

st.markdown("""
### 📘 Så fungerar det:
1. Ladda upp en JSON-fil från Insurematch eller klicka på testdata
2. Alternativt – analysera dina PDF-villkor eller försäkringsbrev
3. Vi jämför villkoren och visar rankat resultat
""")

# --- JSON-delen ---
data = []

if st.button("📊 Visa testdata"):
    exempeldata = [
        {"försäkringsgivare": "TryggHansa", "egendom": "10 MSEK", "ansvar": "20 MSEK", "avbrott": "50 MSEK", "självrisk": "50k", "undantag": "Cyber, Krig", "premie": "240000 kr", "villkorsreferens": "PDF123"},
        {"försäkringsgivare": "IF", "egendom": "8 000 000 kr", "ansvar": "25 000 000 kr", "avbrott": "45 000 000", "självrisk": "40 000 SEK", "undantag": "Cyber", "premie": "230000", "villkorsreferens": "LINK456"},
        {"försäkringsgivare": "Länsförsäkringar", "egendom": "9 MSEK", "ansvar": "22 MSEK", "avbrott": "48 MSEK", "självrisk": "60k", "undantag": "Cyber, Strejk", "premie": "225000 kr", "villkorsreferens": "DOC789"}
    ]
    data = exempeldata
else:
    uploaded_json = st.file_uploader("📁 Ladda upp JSON-fil", type=["json"])
    if uploaded_json:
        try:
            data = json.load(uploaded_json)
        except Exception as e:
            st.error(f"Fel i JSON: {e}")

# --- PDF-delen ---
with st.expander("📄 Ladda upp PDF för analys (villkor eller försäkringsbrev)"):
    uploaded_pdf = st.file_uploader("📄 Ladda upp PDF", type="pdf")
    if uploaded_pdf:
        pdf_text = läs_pdf_text(uploaded_pdf)
        st.subheader("📃 Utdrag ur PDF:")
        st.text_area("PDF-innehåll", value=pdf_text[:3000], height=300)
        villkor = extrahera_villkor_ur_pdf(pdf_text)
        st.markdown("**📌 Automatisk extraktion:**")
        st.json(villkor)
        data.append(villkor)

# --- Jämförelse & export ---
if data:
    normaliserade = [normalisera_data(f) for f in data]
    rankade = jämför_försäkringar(normaliserade)
    df_resultat = pd.DataFrame(rankade)

    st.success("✅ Jämförelse klar!")
    st.dataframe(df_resultat)

    st.download_button("⬇️ Ladda ner som CSV", data=df_resultat.to_csv(index=False).encode("utf-8"), file_name="forsakringsjamforelse.csv")
    word_buffer = generera_word_dokument(rankade)
    st.download_button("⬇️ Ladda ner upphandlingsunderlag (Word)", data=word_buffer, file_name="upphandlingsunderlag.docx")
else:
    st.info("Ladda upp JSON eller testa PDF-läsning för analys.")
