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
        s = s.replace(",", ".")  # hantera t.ex. 1,5m som 1.5m

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
st.session_state.setdefault("extraherade_villkor", [])

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
                    full_text += page_text + "
"

            st.subheader(f"🔎 PDF {i+1}: {uploaded_pdf.name}")
            st.text_area("📄 PDF-innehåll (formaterat)", value=formattera_pdf_text(full_text)[:3000], height=300)

            extrakt = extrahera_villkor_ur_pdf(full_text)
            st.session_state.extraherade_villkor.append(extrakt)
            st.json(extrakt)

        st.subheader("📊 Jämförelse med poängsättning")
        df = pd.DataFrame(poangsatt_villkor(st.session_state.extraherade_villkor))
        st.dataframe(df.style.background_gradient(subset=["Totalpoäng"], cmap="RdYlGn"))

        st.subheader("📉 Benchmarking")
        st.markdown(f"**Snittpremie:** {df['Premie'].mean():,.0f} kr  |  **Snittsjälvrisk:** {df['Självrisk'].mean():,.0f} kr  |  **Snittpoäng:** {df['Totalpoäng'].mean():.2f}")

        # Export till Word
        from docx import Document
        buffer = BytesIO()
        doc = Document()
        doc.add_heading("Jämförelse av försäkringsofferter", level=1)
        table = doc.add_table(rows=1, cols=len(df.columns))
        for i, col in enumerate(df.columns):
            table.rows[0].cells[i].text = col
        for _, row in df.iterrows():
            cells = table.add_row().cells
            for i, val in enumerate(row):
                cells[i].text = str(val)
        doc.save(buffer)
        buffer.seek(0)
        st.download_button("📥 Ladda ner jämförelse (Word)", data=buffer, file_name="jamforelse.docx")

        st.subheader("🔎 Förhandsvisning av PDF-text")
        st.text_area("📄 PDF-innehåll (formaterat)", value=formattera_pdf_text(full_text)[:3000], height=400)

        st.subheader("📋 Extraherade värden")
        resultat = extrahera_villkor_ur_pdf(full_text)
        st.json(resultat)

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

        st.subheader("📊 Jämförelse med poängsättning")
        df = pd.DataFrame(poangsatt_villkor([resultat]))
        st.dataframe(df.style.background_gradient(subset=["Totalpoäng"], cmap="RdYlGn"))

        st.subheader("📉 Benchmarking")
        st.markdown(f"**Snittpremie:** {df['Premie'].mean():,.0f} kr  |  **Snittsjälvrisk:** {df['Självrisk'].mean():,.0f} kr  |  **Snittpoäng:** {df['Totalpoäng'].mean():.2f}")

# resten av koden oförändrad...
