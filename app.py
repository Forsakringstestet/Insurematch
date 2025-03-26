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
    st.set_page_config(page_title="PDF-analys", layout="centered")
    st.title("📄 PDF-analys och villkorsutdrag")

    uploaded_pdfs = st.file_uploader("Ladda upp en eller flera PDF:er", type="pdf", accept_multiple_files=True)
    if uploaded_pdfs:
        for i, uploaded_pdf in enumerate(uploaded_pdfs):
            reader = PdfReader(uploaded_pdf)
            full_text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"  # Fixat strängfel

            st.subheader(f"🔎 PDF {i+1}: {uploaded_pdf.name}")
            st.text_area("📄 PDF-innehåll (formaterat)", value=formattera_pdf_text(full_text)[:3000], height=300)

            st.subheader("📋 Extraherade värden")
            resultat = extrahera_villkor_ur_pdf(full_text)
            st.json(resultat)

            # Om villkoren inte kunde extraheras korrekt
            saknade = [k for k, v in resultat.items() if to_number(v) == 0 and k != "undantag"]
            if saknade:
                st.warning(f"⚠️ Saknade fält i {uploaded_pdf.name}: {', '.join(saknade)}")

# === Jämförelse och benchmarking ===

    if uploaded_pdfs:
        # Förbered data för poängsättning
        villkorslista = []
        for pdf in uploaded_pdfs:
            text = läs_pdf_text(pdf)
            extrakt = extrahera_villkor_ur_pdf(text)
            villkorslista.append(extrakt)

        st.subheader("📊 Jämförelse med poängsättning")
        df = pd.DataFrame(poangsatt_villkor(villkorslista))
        st.dataframe(df.style.background_gradient(subset=["Totalpoäng"], cmap="RdYlGn"))

        st.subheader("📉 Benchmarking")
        st.markdown(f"**Snittpremie:** {df['Premie'].mean():,.0f} kr  |  **Snittsjälvrisk:** {df['Självrisk'].mean():,.0f} kr  |  **Snittpoäng:** {df['Totalpoäng'].mean():.2f}")

        # Ladda ner sammanställning (Word)
        st.download_button("⬇️ Ladda ner sammanställning (Word)", data=generera_word_dokument(df.to_dict(orient="records")), file_name="jamforelse_upphandling.docx")

        # Påminnelse
        påminnelse_datum = st.date_input("🔔 Vill du få en påminnelse innan förnyelse?", value=date.today() + timedelta(days=300), key="reminder_date")
        st.success(f"🔔 Påminnelse noterat: spara detta datum ({påminnelse_datum}) i din kalender")
