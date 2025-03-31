# === Konstanter ===
BASBELOPP_2025 = 58800

# === Hjälpmetoder ===
def to_number(varde):
    try:
        if varde is None:
            return 0
        if isinstance(varde, (int, float)):
            return int(varde)
        s = str(varde).lower().replace(" ", "").replace(",", ".").replace("sek", "").replace("kr", "")
        if "basbelopp" in s or "bb" in s:
            return int(float(re.findall(r"(\d+\.?\d*)", s)[0]) * BASBELOPP_2025)
        if "msek" in s or "miljoner" in s:
            return int(float(re.findall(r"(\d+\.?\d*)", s)[0]) * 1_000_000)
        if "k" in s:
            return int(float(re.findall(r"(\d+\.?\d*)", s)[0]) * 1_000)
        digits = ''.join(filter(lambda x: x.isdigit() or x == '.', s))
        return int(float(digits)) if digits else 0
    except:
        return 0

def extract_multiple_amounts(pattern, text):
    return sum([to_number(val) for val in re.findall(pattern, text)])
# === Parser för IF-försäkringen ===
def extrahera_if_forsakring(text):
    def belopp(pattern, fallback=0):
        match = re.search(pattern, text)
        return to_number(match.group(1)) if match else fallback

    data = {
        "forsakringsgivare": "IF",
        "forsakringsnummer": re.search(r"försäkringsnummer[:\s]+([a-z0-9.\-]+)", text).group(1),
        "forsakringstid": re.search(r"försäkringstid[:\s]+([0-9\-]+\s*-\s*[0-9\-]+)", text).group(1),
        "premie": belopp(r"totalt sek ([\d\s]+)"),
        "självrisk": belopp(r"självrisk.*?([\d\s]+) kr"),

        # Egendom
        "egendom_byggnad": belopp(r"byggnad.*?röjningskostnad.*?([\d\s]+) kr"),
        "egendom_maskiner": belopp(r"maskiner.*?försäkringsbelopp:\s+([\d\s]+) kr"),
        "egendom_varor": belopp(r"varor.*?försäkringsbelopp:\s+([\d\s]+) kr"),

        # Avbrott
        "avbrott_tackningsbidrag": belopp(r"omsättning:\s+([\d\s]+) kr"),
        "avbrott_intaktsbortfall": belopp(r"avbrott.*?försäkringsbelopp:\s+([\d\s]+) kr"),

        # Ansvar
        "ansvar_produkt": extract_multiple_amounts(r"produktansvar.*?försäkringsbelopp.*?:\s+([\d\s]+) kr", text),
        "ansvar_allmant": extract_multiple_amounts(r"verksamhetsansvar.*?försäkringsbelopp.*?:\s+([\d\s]+) kr", text),# === Poängsättning & benchmarking ===
def poangsatt_villkor(lista):
    import pandas as pd
    df = pd.DataFrame(lista)

    df["Premie"] = df["premie"].apply(to_number)
    df["Självrisk"] = df["självrisk"].apply(to_number)
    df["Egendom"] = df["forsakringsbelopp_egendom"]
    df["Ansvar"] = df["forsakringsbelopp_ansvar"]
    df["Avbrott"] = df["forsakringsbelopp_avbrott"]

    max_p, max_s, max_e, max_a, max_v = df["Premie"].max(), df["Självrisk"].max(), df["Egendom"].max(), df["Ansvar"].max(), df["Avbrott"].max()
    maxify = lambda v, m: round((v / m * 10) if m else 0, 2)
    minify = lambda v, m: round((1 - v / m) * 10 if m else 0, 2)

    df["Poäng_premie"] = df["Premie"].apply(lambda x: minify(x, max_p))
    df["Poäng_självrisk"] = df["Självrisk"].apply(lambda x: minify(x, max_s))
    df["Poäng_egendom"] = df["Egendom"].apply(lambda x: maxify(x, max_e))
    df["Poäng_ansvar"] = df["Ansvar"].apply(lambda x: maxify(x, max_a))
    df["Poäng_avbrott"] = df["Avbrott"].apply(lambda x: maxify(x, max_v))

    df["Totalpoäng"] = df[["Poäng_premie", "Poäng_självrisk", "Poäng_egendom", "Poäng_ansvar", "Poäng_avbrott"]].mean(axis=1).round(2)

    df_sorted = df.sort_values(by="Totalpoäng", ascending=False).reset_index(drop=True)

    benchmark = {
        "Snittpremie": int(df["Premie"].mean()),
        "Snittsjälvrisk": int(df["Självrisk"].mean()),
        "Snittpoäng": round(df["Totalpoäng"].mean(), 2)
    }
    # Summeringar
    data["forsakringsbelopp_egendom"] = sum([
        to_number(data["egendom_byggnad"]),
        to_number(data["egendom_maskiner"]),
        to_number(data["egendom_varor"]),
    ])
    data["forsakringsbelopp_avbrott"] = sum([
        to_number(data["avbrott_tackningsbidrag"]),
        to_number(data["avbrott_intaktsbortfall"]),
    ])
    data["forsakringsbelopp_ansvar"] = sum([
        to_number(data["ansvar_produkt"]),
        to_number(data["ansvar_allmant"]),
    ])

    return data

# === Parser för LF-försäkringen (Gjensidige) ===
def extrahera_lf_forsakring(text):
    def belopp(pattern, fallback=0):
        match = re.search(pattern, text)
        return to_number(match.group(1)) if match else fallback

    data = {
        "forsakringsgivare": "LF",
        "forsakringsnummer": "Offert 2317678",
        "forsakringstid": "2025-04-01 - 2026-04-01",
        "premie": belopp(r"pris per år\s+([\d\s]+)"),
        "självrisk": belopp(r"självrisk.*?(\d+% av pbb)"),
        "egendom_byggnad": belopp(r"trädgård & tomtmark:\s+([\d\s]+)"),
        "egendom_maskiner": belopp(r"maskinerier:\s+([\d\s]+)"),
        "egendom_varor": belopp(r"varor:\s+([\d\s]+)"),
        "avbrott_tackningsbidrag": belopp(r"omsättning\s+([\d\s]+)"),
        "avbrott_intaktsbortfall": belopp(r"avbrott.*?([\d\s]+)"),
        "ansvar_produkt": belopp(r"produktansvar\s+([\d\s]+)"),
        "ansvar_allmant": belopp(r"verksamhetsansvar.*?([\d\s]+)"),
    }

    data["forsakringsbelopp_egendom"] = sum([
        to_number(data["egendom_byggnad"]),
        to_number(data["egendom_maskiner"]),
        to_number(data["egendom_varor"]),
    ])
    data["forsakringsbelopp_avbrott"] = sum([
        to_number(data["avbrott_tackningsbidrag"]),
        to_number(data["avbrott_intaktsbortfall"]),
    ])
    data["forsakringsbelopp_ansvar"] = sum([
        to_number(data["ansvar_produkt"]),
        to_number(data["ansvar_allmant"]),
    ])

    return data
    # === Parser för TH-försäkringen (Trygg-Hansa) ===
def extrahera_th_forsakring(text):
    def belopp(pattern, fallback=0):
        match = re.search(pattern, text)
        return to_number(match.group(1)) if match else fallback

    data = {
        "forsakringsgivare": "Trygg-Hansa",
        "forsakringsnummer": "25-3553726-01",
        "forsakringstid": "2025-04-01 - 2026-04-01",
        "premie": belopp(r"pris totalt:\s+([\d\s]+)"),
        "självrisk": belopp(r"självrisk.*?(\d+\.?\d* basbelopp)"),
        "egendom_byggnad": belopp(r"byggnad.*?allriskförsäkring.*?(\d+\.?\d* basbelopp)"),
        "egendom_maskiner": belopp(r"maskiner/inventarier.*?-\s+([\d\s]+) kr"),
        "egendom_varor": belopp(r"varor.*?-\s+([\d\s]+) kr"),
        "avbrott_tackningsbidrag": belopp(r"omsättning.*?([\d\s]+) kr"),
        "avbrott_intaktsbortfall": 0,
        "ansvar_produkt": belopp(r"produktansvar.*?-\s+([\d\s]+) kr"),
        "ansvar_allmant": belopp(r"ansvarsförsäkring.*?-\s+([\d\s]+) kr"),
    }

    data["forsakringsbelopp_egendom"] = sum([
        to_number(data["egendom_byggnad"]),
        to_number(data["egendom_maskiner"]),
        to_number(data["egendom_varor"]),
    ])
    data["forsakringsbelopp_avbrott"] = sum([
        to_number(data["avbrott_tackningsbidrag"]),
        to_number(data["avbrott_intaktsbortfall"]),
    ])
    data["forsakringsbelopp_ansvar"] = sum([
        to_number(data["ansvar_produkt"]),
        to_number(data["ansvar_allmant"]),
    ])

    return data
     return df_sorted, benchmark
# === Poängsättning & benchmarking ===
def poangsatt_villkor(lista):
    import pandas as pd
    df = pd.DataFrame(lista)

    df["Premie"] = df["premie"].apply(to_number)
    df["Självrisk"] = df["självrisk"].apply(to_number)
    df["Egendom"] = df["forsakringsbelopp_egendom"]
    df["Ansvar"] = df["forsakringsbelopp_ansvar"]
    df["Avbrott"] = df["forsakringsbelopp_avbrott"]

    max_p, max_s, max_e, max_a, max_v = df["Premie"].max(), df["Självrisk"].max(), df["Egendom"].max(), df["Ansvar"].max(), df["Avbrott"].max()
    maxify = lambda v, m: round((v / m * 10) if m else 0, 2)
    minify = lambda v, m: round((1 - v / m) * 10 if m else 0, 2)

    df["Poäng_premie"] = df["Premie"].apply(lambda x: minify(x, max_p))
    df["Poäng_självrisk"] = df["Självrisk"].apply(lambda x: minify(x, max_s))
    df["Poäng_egendom"] = df["Egendom"].apply(lambda x: maxify(x, max_e))
    df["Poäng_ansvar"] = df["Ansvar"].apply(lambda x: maxify(x, max_a))
    df["Poäng_avbrott"] = df["Avbrott"].apply(lambda x: maxify(x, max_v))

    df["Totalpoäng"] = df[["Poäng_premie", "Poäng_självrisk", "Poäng_egendom", "Poäng_ansvar", "Poäng_avbrott"]].mean(axis=1).round(2)

    df_sorted = df.sort_values(by="Totalpoäng", ascending=False).reset_index(drop=True)

    benchmark = {
        "Snittpremie": int(df["Premie"].mean()),
        "Snittsjälvrisk": int(df["Självrisk"].mean()),
        "Snittpoäng": round(df["Totalpoäng"].mean(), 2)
    }

    return df_sorted, benchmark

# === UI-styling (Streamlit) ===
def fargstil(value):
    if value >= 8:
        return 'background-color: #c4f5c2'
    elif value >= 6:
        return 'background-color: #fff4a3'
    elif value >= 4:
        return 'background-color: #ffd2a3'
    else:
        return 'background-color: #ffb6b6'

def render_resultat(df, benchmark, st):
    from io import BytesIO
    from docx import Document
    import json

    st.subheader("📊 Sammanställning & poängsättning")
    st.dataframe(df.style.applymap(fargstil, subset=["Totalpoäng"]))

    st.subheader("📉 Benchmarking")
    st.markdown(f"**Snittpremie:** {benchmark['Snittpremie']:,} kr  ")
    st.markdown(f"**Snittsjälvrisk:** {benchmark['Snittsjälvrisk']:,} kr  ")
    st.markdown(f"**Snittpoäng:** {benchmark['Snittpoäng']:.2f}")

    st.subheader("⬇️ Export")

    # Exportera till Word
    doc = Document()
    doc.add_heading("Försäkringsjämförelse", level=1)
    table = doc.add_table(rows=1, cols=len(df.columns))
    hdr_cells = table.rows[0].cells
    for i, col in enumerate(df.columns):
        hdr_cells[i].text = col
    for _, row in df.iterrows():
        row_cells = table.add_row().cells
        for i, col in enumerate(df.columns):
            row_cells[i].text = str(row[col])
    word_buf = BytesIO()
    doc.save(word_buf)
    word_buf.seek(0)

    # Exportera till JSON
    json_buf = BytesIO()
    json_buf.write(json.dumps(df.to_dict(orient="records"), indent=2, ensure_ascii=False).encode("utf-8"))
    json_buf.seek(0)

    st.download_button("📄 Ladda ner Word-dokument", data=word_buf, file_name="forsakringsjamforelse.docx")
    st.download_button("🧾 Exportera som JSON", data=json_buf, file_name="forsakringsdata.json")
