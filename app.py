import streamlit as st
import pandas as pd
import json

# Funktioner för databehandling
def to_number(varde):
    if varde is None:
        return 0
    s = str(varde).replace(" ", "").replace("kr", "").replace("SEK", "").replace("k", "000").replace("MSEK", "000000")
    return int(''.join(filter(str.isdigit, s)))

def normalisera_data(radata):
    return {
        "bolag": radata.get("försäkringsgivare"),
        "egendom": to_number(radata.get("egendom", 0)),
        "ansvar": to_number(radata.get("ansvar", 0)),
        "avbrott": to_number(radata.get("avbrott", 0)),
        "självrisk": to_number(radata.get("självrisk", 0)),
        "undantag": [u.strip().lower() for u in radata.get("undantag", "").split(",")],
        "premie": to_number(radata.get("premie", 0)),
        "villkor_id": radata.get("villkorsreferens")
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

# Streamlit-gränssnitt
st.title("Försäkringsjämförelse – Upphandling")

st.write("Ladda upp en JSON-fil med försäkringsdata (från Insurematch eller annan källa)")

uploaded_file = st.file_uploader("Välj fil", type=["json"])

if uploaded_file is not None:
    try:
        rådata = json.load(uploaded_file)
        normaliserade = [normalisera_data(f) for f in rådata]
        rankade = jämför_försäkringar(normaliserade)

        df_resultat = pd.DataFrame(rankade)
        st.subheader("Rankade försäkringar")
        st.dataframe(df_resultat)

        st.download_button(
            label="Ladda ner resultat som CSV",
            data=df_resultat.to_csv(index=False).encode("utf-8"),
            file_name="forsakringsjamforelse.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"Något gick fel vid tolkning av filen: {e}")
else:
    st.info("Vänligen ladda upp en JSON-fil för att se resultat")
